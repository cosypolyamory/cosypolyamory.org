"""
Admin API endpoints

Handles admin-specific API operations like user management, role changes, etc.
"""

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from cosypolyamory.models.user import User
from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.models.event import Event
from cosypolyamory.models.rsvp import RSVP
from cosypolyamory.database import database
from cosypolyamory.notification import send_notification_email
from cosypolyamory.email import EmailError

bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator to require admin role"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_organize_events():
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/admin/users/<role>')
@admin_required
def api_admin_users_by_role(role):
    """Return paginated list of users by role"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Validate role
        valid_roles = ['pending', 'approved', 'organizer', 'rejected', 'admin', 'new']
        if role == 'pending':
            # Show both 'pending' and 'new' users under the pending tab
            # Fetch all users with role 'pending' or 'new'
            all_pending_new = list(User.select().where(User.role.in_(['pending', 'new'])))
            # Split into those with an application and those without
            with_pending_app = []
            without_pending_app = []
            for user in all_pending_new:
                application = UserApplication.select().where(UserApplication.user == user).first()
                if application:
                    with_pending_app.append((user, application))
                else:
                    without_pending_app.append((user, None))
            # Sort with_pending_app by application.submitted_at ascending (oldest first)
            with_pending_app.sort(key=lambda tup: tup[1].submitted_at if tup[1] else user.created_at)
            # Sort without_pending_app by user.created_at descending (most recent first)
            without_pending_app.sort(key=lambda tup: tup[0].created_at, reverse=True)
            # Merge
            sorted_users = with_pending_app + without_pending_app
            # For pagination
            total = len(sorted_users)
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))
            paged = sorted_users[(page-1)*per_page:page*per_page]
            user_list = []
            for user, application in paged:
                user_list.append({
                    'id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'avatar_url': user.avatar_url,
                    'provider': user.provider,
                    'role': user.role,
                    'created_at': user.created_at.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'has_application': bool(application),
                    'application_id': application.id if application else None,
                    'application_status': application.status if application else None
                })
            return jsonify({
                'users': user_list,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
        elif role in valid_roles:
            query = User.select().where(User.role == role).order_by(User.created_at.desc())
        else:
            return jsonify({'error': 'Invalid role'}), 400
        
        # Calculate pagination
        total = query.count()
        users = query.paginate(page, per_page)
        
        user_list = []
        for user in users:
            # Always get the most recent application for this user
            application = UserApplication.select().where(UserApplication.user == user).order_by(UserApplication.submitted_at.desc()).first()
            user_list.append({
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'avatar_url': user.avatar_url,
                'provider': user.provider,
                'role': user.role,
                'created_at': user.created_at.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'has_application': bool(application),
                'application_id': application.id if application else None,
                'application_status': application.status if application else None
            })
        
        return jsonify({
            'users': user_list,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/admin/user/<user_id>')
@admin_required
def api_user_details(user_id):
    """Return detailed user information"""
    try:
        user = User.get_by_id(user_id)
        return jsonify({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'avatar_url': user.avatar_url,
            'provider': user.provider,
            'role': user.role,
            'pronoun_singular': user.pronoun_singular,
            'pronoun_plural': user.pronoun_plural,
            'created_at': user.created_at.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None
        })
    except User.DoesNotExist:
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/admin/change-role', methods=['POST'])
@admin_required
def api_change_user_role():
    """Change a user's role (admin only)"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_role = data.get('role')
        
        if not user_id or not new_role:
            return jsonify({'success': False, 'error': 'Missing user_id or role'})
        
        if new_role not in ['admin', 'organizer', 'approved', 'new', 'rejected']:
            return jsonify({'success': False, 'error': 'Invalid role'})
        
        # Check if trying to make admin and current user is not admin
        if new_role == 'admin' and not current_user.is_admin:
            return jsonify({'success': False, 'error': 'Only admins can make other users admin'})
        
        # Find the user
        try:
            user = User.get(User.id == user_id)
        except User.DoesNotExist:
            return jsonify({'success': False, 'error': 'User not found'})
        
        # Special handling for users being marked as pending/new - clear their application data
        old_role = user.role
        
        # Update user role and corresponding boolean flags
        with database.atomic():
            # If changing to pending, clear their application data and mark as "new"
            if new_role == 'new':
                # Delete any existing application
                try:
                    application = UserApplication.get(UserApplication.user == user)
                    application.delete_instance()
                except UserApplication.DoesNotExist:
                    pass  # No application to delete
                
                # Set role to 'new' instead of 'pending' to indicate fresh start
                user.role = 'new'
            else:
                user.role = new_role
            
            user.is_admin = (user.role == 'admin')
            user.is_organizer = (user.role == 'organizer')
            user.is_approved = (user.role in ['admin', 'organizer', 'approved'])
            user.save()
        
        # Send notifications for role changes
        try:
            # Member becoming organizer
            if old_role == 'approved' and user.role == 'organizer':
                send_notification_email(
                    user.email,
                    'role_change_organizer',
                    user=user,
                    old_role='Member',
                    new_role='Organizer'
                )
            
            # Organizer becoming regular member  
            elif old_role == 'organizer' and user.role == 'approved':
                send_notification_email(
                    user.email,
                    'role_change_member',
                    user=user,
                    old_role='Organizer',
                    new_role='Member'
                )
            
            # User marked as new (with application data removed)
            elif user.role == 'new' and old_role in ['rejected', 'pending', 'approved', 'organizer']:
                send_notification_email(
                    user.email,
                    'role_change_new',
                    user=user,
                    old_role=old_role.title(),
                    application_removed=True
                )
                
        except EmailError as e:
            # Log the error but don't fail the role change
            current_app.logger.error(f"Failed to send role change notification to {user.email}: {str(e)}")
        except Exception as e:
            # Log any other email errors but don't fail the role change
            current_app.logger.error(f"Unexpected error sending role change notification to {user.email}: {str(e)}")
        
        return jsonify({
            'success': True, 
            'message': f'User role changed to {user.role}',
            'user_id': user_id,
            'new_role': user.role
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/admin/delete-user', methods=['POST'])
@admin_required
def api_delete_user():
    """Delete a user (admin only)"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Missing user_id'})
        
        # Find the user
        try:
            user = User.get(User.id == user_id)
        except User.DoesNotExist:
            return jsonify({'success': False, 'error': 'User not found'})
        
        # Prevent self-deletion
        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot delete your own account'})
        
        # Prevent deletion of admin users and system accounts
        if user.role == 'admin':
            return jsonify({'success': False, 'error': 'Admin users cannot be deleted'})
        
        # Prevent deletion of the system "Deleted User" placeholder
        if user.role == 'deleted' or user.id == 'system_deleted_user':
            return jsonify({'success': False, 'error': 'System accounts cannot be deleted'})
        
        # Check if user is hosting/co-hosting any events
        organized_events = list(Event.select().where(Event.organizer == user))
        co_hosted_events = list(Event.select().where(Event.co_host == user))
        
        if organized_events or co_hosted_events:
            # Build detailed error message with event links
            error_message = f"Cannot delete {user.name} because they are still hosting events. Please reassign these events first:"
            event_details = []
            
            for event in organized_events:
                event_details.append({
                    'id': event.id,
                    'title': event.title,
                    'date': event.date.strftime('%Y-%m-%d'),
                    'role': 'Organizer'
                })
            
            for event in co_hosted_events:
                event_details.append({
                    'id': event.id,
                    'title': event.title,
                    'date': event.date.strftime('%Y-%m-%d'),
                    'role': 'Co-host'
                })
            
            return jsonify({
                'success': False, 
                'error': error_message,
                'hosted_events': event_details
            })

        # Delete related records first (UserApplication, RSVP, etc.)
        with database.atomic():
            # Delete user applications
            UserApplication.delete().where(UserApplication.user == user).execute()
            
            # Delete RSVPs
            RSVP.delete().where(RSVP.user == user).execute()
            
            # Delete the user
            user_name = user.name
            user.delete_instance()
        
        return jsonify({
            'success': True, 
            'message': f'User {user_name} deleted successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/admin/event-note/<int:note_id>/usage')
@admin_required
def check_event_note_usage(note_id):
    """Check if an event note is being used by any events"""
    try:
        from cosypolyamory.models.event_note import EventNote
        
        # Verify the note exists
        try:
            note = EventNote.get_by_id(note_id)
        except EventNote.DoesNotExist:
            return jsonify({'success': False, 'error': 'Event note not found'}), 404
        
        # Find all events using this note
        events_using_note = list(Event.select().where(Event.event_note == note))
        
        # Format event information
        events_data = []
        for event in events_using_note:
            events_data.append({
                'id': event.id,
                'title': event.title,
                'exact_time': event.exact_time.isoformat()
            })
        
        return jsonify({
            'success': True,
            'note_id': note_id,
            'note_name': note.name,
            'events_using_note': events_data,
            'can_delete': len(events_data) == 0
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
