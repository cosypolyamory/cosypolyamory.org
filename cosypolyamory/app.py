#!/usr/bin/env python3

import os
import json
import sys
import re
import urllib.parse
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, send_file, session, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

# Import database and models
from cosypolyamory.database import init_database
from cosypolyamory.models.user import User
from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.models.event import Event
from cosypolyamory.models.rsvp import RSVP

# Load environment variables
load_dotenv()

STATIC_PATH = "/static"
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static')
TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), 'templates')

app = Flask(__name__,
            static_url_path = STATIC_PATH,
            static_folder = STATIC_FOLDER,
            template_folder = TEMPLATE_FOLDER)

# Configure Flask app
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize database
init_database()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Initialize OAuth
oauth = OAuth(app)

# Configure OAuth providers
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v2/',
    client_kwargs={'scope': 'openid email profile'},
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
)

github = oauth.register(
    name='github',
    client_id=os.getenv('GITHUB_CLIENT_ID'),
    client_secret=os.getenv('GITHUB_CLIENT_SECRET'),
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

reddit = oauth.register(
    name='reddit',
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    access_token_url='https://www.reddit.com/api/v1/access_token',
    authorize_url='https://www.reddit.com/api/v1/authorize',
    api_base_url='https://oauth.reddit.com/',
    client_kwargs={'scope': 'identity'},
    token_endpoint_auth_method='client_secret_basic',  # Reddit requires basic auth
)

# In-memory user storage replaced with database
# users = {} - removed

def extract_google_maps_info(maps_url):
    """Extract coordinates or place information from Google Maps URL"""
    if not maps_url:
        return None
    
    try:
        # If it's a short URL, resolve it first
        if 'goo.gl' in maps_url or 'maps.app.goo.gl' in maps_url:
            try:
                import urllib.request as url_request
                req = url_request.Request(maps_url)
                req.add_header('User-Agent', 'Mozilla/5.0 (compatible; bot)')
                with url_request.urlopen(req) as response:
                    maps_url = response.geturl()
                    print(f"Resolved short URL to: {maps_url}")
            except Exception as e:
                print(f"Could not resolve short URL: {e}")
                # Fall back to search mode if resolution fails
                return {'search_url': maps_url}
        
        # Try to extract coordinates from various Google Maps URL formats
        # Format 1: /@lat,lng,zoom
        coord_pattern = r'/@(-?\d+\.?\d*),(-?\d+\.?\d*),\d+\.?\d*z'
        coord_match = re.search(coord_pattern, maps_url)
        if coord_match:
            lat, lng = coord_match.groups()
            return {'lat': float(lat), 'lng': float(lng)}
        
        # Format 2: /place/Name/@lat,lng
        place_coord_pattern = r'/place/[^/@]+/@(-?\d+\.?\d*),(-?\d+\.?\d*)'
        place_coord_match = re.search(place_coord_pattern, maps_url)
        if place_coord_match:
            lat, lng = place_coord_match.groups()
            return {'lat': float(lat), 'lng': float(lng)}
        
        # Format 3: URL parameters like 3d41.381138!4d2.186112
        param_coord_pattern = r'3d(-?\d+\.?\d*)!4d(-?\d+\.?\d*)'
        param_coord_match = re.search(param_coord_pattern, maps_url)
        if param_coord_match:
            lat, lng = param_coord_match.groups()
            return {'lat': float(lat), 'lng': float(lng)}
        
        # Format 4: Extract place ID for places
        place_id_pattern = r'place/([^/@?]+)'
        place_match = re.search(place_id_pattern, maps_url)
        if place_match:
            place_name = urllib.parse.unquote(place_match.group(1)).replace('+', ' ')
            return {'place_name': place_name}
            
        # Format 5: Query parameter format ?q=location
        query_pattern = r'[?&]q=([^&]+)'
        query_match = re.search(query_pattern, maps_url)
        if query_match:
            place_name = urllib.parse.unquote(query_match.group(1)).replace('+', ' ')
            return {'place_name': place_name}
            
    except Exception as e:
        print(f"Error parsing Google Maps URL: {e}")
    
    return None

@login_manager.user_loader
def load_user(user_id):
    """Load user from database"""
    try:
        return User.get(User.id == user_id)
    except User.DoesNotExist:
        return None

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        # Check if user has admin status in database
        if not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def organizer_required(f):
    """Decorator to require organizer access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.can_organize_events():
            flash('Organizer access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_or_organizer_required(f):
    """Decorator to require admin or organizer access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.can_organize_events():
            flash('Admin or Organizer access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def approved_user_required(f):
    """Decorator to require approved user status"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': 'Please log in to continue.'})
            return redirect(url_for('login'))
        if current_user.role not in ['approved', 'admin', 'organizer']:
            message = 'Community approval required to access this feature.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'info')
            return redirect(url_for('application_status'))
        return f(*args, **kwargs)
    return decorated_function

# API Routes for AJAX requests
@app.route('/api/user')
@login_required
def api_user():
    """Return current user information as JSON"""
    return jsonify({
        'id': current_user.id,
        'email': current_user.email,
        'name': current_user.name,
        'avatar_url': current_user.avatar_url,
        'provider': current_user.provider,
        'created_at': current_user.created_at.isoformat(),
        'is_approved': current_user.is_approved,
        'is_organizer': current_user.is_organizer,
        'is_admin': current_user.is_admin,
        'role': current_user.get_role_display()
    })

@app.route('/api/users/search')
@login_required
def search_users():
    """Search for users by name or email (for autocomplete)"""
    try:
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 10)), 50)  # Max 50 results
        
        if not query or len(query) < 2:
            return jsonify([])
        
        # Search in name and email fields using Peewee ORM
        search_pattern = f"%{query}%"
        
        # Get users matching the search query
        users = (User.select()
                    .where((User.name.ilike(search_pattern) | User.email.ilike(search_pattern))
                           & (User.role != 'new'))
                    .order_by(User.name.asc())
                    .limit(limit))
        
        result = []
        for user in users:
            # Map role to display name
            role_display = {
                'pending': 'Pending',
                'approved': 'Member', 
                'organizer': 'Organizer',
                'admin': 'Admin',
                'rejected': 'Rejected'
            }.get(user.role, user.role.title())
            
            result.append({
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'role_display': role_display,
                'avatar_url': getattr(user, 'avatar_url', None)
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users/<role>')
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
            from cosypolyamory.models.user_application import UserApplication
            # Split into those with a pending application and those without
            with_pending_app = []
            without_pending_app = []
            for user in all_pending_new:
                application = UserApplication.select().where((UserApplication.user == user) & (UserApplication.status == 'pending')).first()
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
        from cosypolyamory.models.user_application import UserApplication
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

@app.route('/api/user/<user_id>')
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
            'created_at': user.created_at.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None
        })
    except User.DoesNotExist:
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/change-role', methods=['POST'])
@admin_required
def api_change_user_role():
    """Change a user's role (admin only)"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_role = data.get('role')
        
        if not user_id or not new_role:
            return jsonify({'success': False, 'error': 'Missing user_id or role'})
        
        if new_role not in ['admin', 'organizer', 'approved', 'pending', 'rejected']:
            return jsonify({'success': False, 'error': 'Invalid role'})
        
        # Check if trying to make admin and current user is not admin
        if new_role == 'admin' and not current_user.is_admin:
            return jsonify({'success': False, 'error': 'Only admins can make other users admin'})
        
        # Find the user
        try:
            user = User.get(User.id == user_id)
        except User.DoesNotExist:
            return jsonify({'success': False, 'error': 'User not found'})
        
        # Update user role and corresponding boolean flags
        user.role = new_role
        user.is_admin = (new_role == 'admin')
        user.is_organizer = (new_role == 'organizer')
        user.is_approved = (new_role in ['admin', 'organizer', 'approved'])
        
        user.save()
        
        return jsonify({
            'success': True, 
            'message': f'User role changed to {new_role}',
            'user_id': user_id,
            'new_role': new_role
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/delete-user', methods=['POST'])
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
        from cosypolyamory.models.event import Event
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
        from cosypolyamory.models.user_application import UserApplication
        from cosypolyamory.models.rsvp import RSVP
        
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

# Application System Routes
@app.route('/apply')
@login_required
def apply():
    """Community application form"""
    # Check if user already has an application
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        return redirect(url_for('application_status'))
    except UserApplication.DoesNotExist:
        pass
    
    # Get questions from environment
    questions = {
        'question_1': os.getenv('APPLICATION_QUESTION_1', 'Question 1'),
        'question_2': os.getenv('APPLICATION_QUESTION_2', 'Question 2'),
        'question_3': os.getenv('APPLICATION_QUESTION_3', 'Question 3'),
        'question_4': os.getenv('APPLICATION_QUESTION_4', 'Question 4'),
        'question_5': os.getenv('APPLICATION_QUESTION_5', 'Question 5'),
        'question_6': os.getenv('APPLICATION_QUESTION_6', 'Question 6'),
        'question_7': os.getenv('APPLICATION_QUESTION_7', 'Question 7'),
    }
    
    return render_template('user/apply.html', questions=questions)

@app.route('/apply', methods=['POST'])
@login_required
def submit_application():
    """Submit community application"""
    # Check if user already has an application
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        flash('You have already submitted an application.', 'info')
        return redirect(url_for('application_status'))
    except UserApplication.DoesNotExist:
        pass
    
    # Create application
    application = UserApplication.create(
        user=current_user,
        question_1_answer=request.form.get('question_1', ''),
        question_2_answer=request.form.get('question_2', ''),
        question_3_answer=request.form.get('question_3', ''),
        question_4_answer=request.form.get('question_4', ''),
        question_5_answer=request.form.get('question_5', ''),
        question_6_answer=request.form.get('question_6', ''),
        question_7_answer=request.form.get('question_7', ''),
    )
    # Set user role to 'pending' after application submission
    current_user.role = 'pending'
    current_user.save()
    flash('Your application has been submitted! You will be notified once it has been reviewed.', 'success')
    return redirect(url_for('application_status'))

@app.route('/application-status')
@login_required
def application_status():
    """Show user's application status"""
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        return render_template('user/application_status.html', application=application)
    except UserApplication.DoesNotExist:
        return redirect(url_for('apply'))

# Moderation Routes
@app.route('/moderate')
@organizer_required
def moderate_applications():
    """Application review queue - only show pending applications with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get paginated pending applications
    pending_applications_query = UserApplication.select().where(UserApplication.status == 'pending').order_by(UserApplication.submitted_at)
    total_applications = pending_applications_query.count()
    
    # Calculate pagination
    offset = (page - 1) * per_page
    pending_applications = list(pending_applications_query.offset(offset).limit(per_page))
    
    # Calculate pagination info
    total_pages = (total_applications + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages
    prev_num = page - 1 if has_prev else None
    next_num = page + 1 if has_next else None
    
    # Get questions from environment for display
    questions = {
        'question_1': os.getenv('APPLICATION_QUESTION_1', 'Question 1'),
        'question_2': os.getenv('APPLICATION_QUESTION_2', 'Question 2'),
        'question_3': os.getenv('APPLICATION_QUESTION_3', 'Question 3'),
        'question_4': os.getenv('APPLICATION_QUESTION_4', 'Question 4'),
        'question_5': os.getenv('APPLICATION_QUESTION_5', 'Question 5'),
        'question_6': os.getenv('APPLICATION_QUESTION_6', 'Question 6'),
        'question_7': os.getenv('APPLICATION_QUESTION_7', 'Question 7'),
    }
    
    return render_template('admin/moderate.html',
                         pending_applications=pending_applications,
                         pending_count=total_applications,
                         questions=questions,
                         pagination={
                             'page': page,
                             'per_page': per_page,
                             'total': total_applications,
                             'pages': total_pages,
                             'has_prev': has_prev,
                             'has_next': has_next,
                             'prev_num': prev_num,
                             'next_num': next_num
                         })

@app.route('/moderate/<int:application_id>/approve', methods=['POST'])
@organizer_required
def approve_application(application_id):
    """Approve a user application"""
    try:
        application = UserApplication.get_by_id(application_id)
        application.status = 'approved'
        application.reviewed_at = datetime.now()
        application.reviewed_by = current_user
        application.review_notes = request.form.get('notes', '')
        application.save()
        
        # Update user status
        user = application.user
        user.is_approved = True
        user.save()
        
        flash(f'Application for {user.name} has been approved.', 'success')
    except UserApplication.DoesNotExist:
        flash('Application not found.', 'error')
    
    return redirect(url_for('moderate_applications'))

@app.route('/moderate/<int:application_id>/reject', methods=['POST'])
@organizer_required
def reject_application(application_id):
    """Reject a user application"""
    try:
        application = UserApplication.get_by_id(application_id)
        application.status = 'rejected'
        application.reviewed_at = datetime.now()
        application.reviewed_by = current_user
        application.review_notes = request.form.get('notes', '')
        application.save()
        
        flash(f'Application for {application.user.name} has been rejected.', 'info')
    except UserApplication.DoesNotExist:
        flash('Application not found.', 'error')
    
    return redirect(url_for('moderate_applications'))

# Events System Routes
@app.route('/events')
def events_list():
    """List all events with appropriate visibility"""
    from datetime import datetime
    events = Event.select().where(Event.is_active == True).order_by(Event.exact_time)
    can_see_details = current_user.is_authenticated and current_user.can_see_full_event_details()
    
    # Get user RSVPs for easy access in template
    user_rsvps = {}
    if current_user.is_authenticated and current_user.role in ['approved', 'admin', 'organizer']:
        rsvps = RSVP.select().where(RSVP.user == current_user)
        user_rsvps = {rsvp.event.id: rsvp for rsvp in rsvps}
    
    # Get RSVP counts for each event
    rsvp_counts = {}
    for event in events:
        count = RSVP.select().where(RSVP.event == event, RSVP.status == 'yes').count()
        rsvp_counts[event.id] = count
    
    return render_template('events/events_list.html', 
                         events=events, 
                         can_see_details=can_see_details,
                         user_rsvps=user_rsvps,
                         rsvp_counts=rsvp_counts,
                         now=datetime.now())

@app.route('/events/<int:event_id>')
@approved_user_required
def event_detail(event_id):
    """Show event details"""
    try:
        event = Event.get_by_id(event_id)
        can_see_details = current_user.is_authenticated and current_user.can_see_full_event_details()
        
        # Get user's RSVP if exists and user is authenticated
        user_rsvp = None
        if current_user.is_authenticated:
            try:
                user_rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == current_user))
            except RSVP.DoesNotExist:
                pass
        
        # Get RSVP counts  
        rsvp_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
        rsvp_no_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).count()
        
        # Get RSVPs for attendees list (only "yes" RSVPs)
        rsvps = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).order_by(RSVP.created_at)
        
        # Get RSVPs for non-attendees list (only "no" RSVPs)
        rsvps_no = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).order_by(RSVP.created_at)
        
        # Extract Google Maps information
        google_maps_info = extract_google_maps_info(event.google_maps_link) if event.google_maps_link else None
        
        from datetime import datetime
        return render_template('events/event_detail.html', 
                             event=event, 
                             can_see_details=can_see_details,
                             user_rsvp=user_rsvp,
                             rsvp_count=rsvp_count,
                             rsvp_no_count=rsvp_no_count,
                             rsvps=rsvps,
                             rsvps_no=rsvps_no,
                             google_maps_api_key=os.getenv('GOOGLE_MAPS_API_KEY'),
                             google_maps_info=google_maps_info,
                             now=datetime.now())
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events_list'))

@app.route('/events/create')
@organizer_required
def create_event():
    """Create new event form"""
    # Get organizers to pass to template
    organizers = User.select().where(User.role.in_(['admin', 'organizer']))
    organizer_list = []
    for organizer in organizers:
        organizer_list.append({
            'id': organizer.id,
            'name': organizer.name,
            'role': organizer.role,
            'is_current_user': organizer.id == current_user.id
        })
    organizer_list.sort(key=lambda x: x['name'])
    
    # Get event notes for dropdown
    from cosypolyamory.models.event_note import EventNote
    event_notes = list(EventNote.select().order_by(EventNote.name))
    return render_template('events/create_event.html', organizers=organizer_list, event_notes=event_notes)

@app.route('/events/create', methods=['POST'])
@organizer_required
def create_event_post():
    """Create new event"""
    from datetime import datetime as dt
    
    try:
        # Parse the form data
        title = request.form.get('title')
        description = request.form.get('description')
        barrio = request.form.get('barrio')
        time_period = request.form.get('time_period')
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        establishment_name = request.form.get('establishment_name')
        google_maps_link = request.form.get('google_maps_link')
        location_notes = request.form.get('location_notes')
        tips_for_attendees = request.form.get('tips_for_attendees')
        max_attendees = request.form.get('max_attendees')
        organizer_id = request.form.get('organizer_id')
        co_host_id = request.form.get('co_host_id', '')
        
        # Validate organizer
        if not organizer_id:
            flash('Please select a primary organizer.', 'error')
            return redirect(url_for('create_event'))
            
        try:
            organizer = User.get_by_id(organizer_id)
            if not organizer.can_organize_events():
                flash('Selected organizer does not have permission to organize events.', 'error')
                return redirect(url_for('create_event'))
        except User.DoesNotExist:
            flash('Selected organizer not found.', 'error')
            return redirect(url_for('create_event'))
        
        # Check permission: only admins or the selected organizer can create events for that organizer
        if not (current_user.role == 'admin' or current_user.id == organizer_id):
            flash('You can only create events as yourself unless you are an admin.', 'error')
            return redirect(url_for('create_event'))
        
        # Parse dates and times
        date = dt.strptime(date_str, '%Y-%m-%d')
        exact_time = dt.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
        
        # Validate Google Maps link if provided
        valid_maps_domains = ['maps.google.com', 'www.google.com/maps', 'maps.app.goo.gl', 'goo.gl/maps']
        if google_maps_link:
            is_valid_maps_link = any(domain in google_maps_link.lower() for domain in valid_maps_domains)
            if not is_valid_maps_link:
                flash('If provided, Google Maps link must be from Google Maps (maps.google.com, www.google.com/maps, or maps.app.goo.gl).', 'error')
                return redirect(url_for('create_event'))
        
        # Handle co-host
        co_host = None
        if co_host_id:
            try:
                co_host = User.get_by_id(co_host_id)
                if not co_host.can_organize_events():
                    flash('Co-host must be an organizer.', 'error')
                    return redirect(url_for('create_event'))
            except User.DoesNotExist:
                flash('Co-host not found.', 'error')
                return redirect(url_for('create_event'))
        
        # Handle event note
        event_note_id = request.form.get('event_note_id')
        event_note = None
        if event_note_id:
            try:
                event_note = EventNote.get_by_id(event_note_id)
            except EventNote.DoesNotExist:
                flash('Selected event note not found.', 'error')
                return redirect(url_for('create_event'))

        # Create event
        event = Event.create(
            title=title,
            description=description,
            barrio=barrio,
            time_period=time_period,
            date=date,
            establishment_name=establishment_name,
            google_maps_link=google_maps_link,
            location_notes=location_notes or None,
            exact_time=exact_time,
            organizer=organizer,
            co_host=co_host,
            tips_for_attendees=tips_for_attendees.strip() if tips_for_attendees and tips_for_attendees.strip() else None,
            max_attendees=int(max_attendees) if max_attendees else None,
            event_note=event_note
        )
        
        flash(f'Event "{title}" has been created successfully!', 'success')
        return redirect(url_for('event_detail', event_id=event.id))
        
    except ValueError as e:
        flash(f'Error creating event: {str(e)}', 'error')
        return redirect(url_for('create_event'))
    except Exception as e:
        flash(f'Unexpected error: {str(e)}', 'error')
        return redirect(url_for('create_event'))

@app.route('/events/<int:event_id>/edit')
@login_required
def edit_event(event_id):
    """Edit event form"""
    try:
        event = Event.get_by_id(event_id)
        
        # Check permissions - only admin, organizers, or event creator can edit
        if not (current_user.role in ['admin', 'organizer'] or event.organizer_id == current_user.id):
            flash('You do not have permission to edit this event.', 'error')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # Get organizers to pass to template
        organizers = User.select().where(User.role.in_(['admin', 'organizer']))
        organizer_list = []
        for organizer in organizers:
            organizer_list.append({
                'id': organizer.id,
                'name': organizer.name,
                'role': organizer.role,
                'is_current_user': organizer.id == current_user.id
            })
        organizer_list.sort(key=lambda x: x['name'])

        # Get event notes for dropdown
        from cosypolyamory.models.event_note import EventNote
        event_notes = list(EventNote.select().order_by(EventNote.name))
        return render_template('events/create_event.html', event=event, is_edit=True, organizers=organizer_list, event_notes=event_notes)
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events_list'))

@app.route('/events/<int:event_id>/edit', methods=['POST'])
@login_required
def edit_event_post(event_id):
    """Update event"""
    from datetime import datetime as dt
    
    try:
        event = Event.get_by_id(event_id)
        
        # Check permissions
        if not (current_user.role in ['admin', 'organizer'] or event.organizer_id == current_user.id):
            flash('You do not have permission to edit this event.', 'error')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # Parse the form data
        title = request.form.get('title')
        description = request.form.get('description')
        barrio = request.form.get('barrio')
        time_period = request.form.get('time_period')
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        establishment_name = request.form.get('establishment_name')
        google_maps_link = request.form.get('google_maps_link')
        location_notes = request.form.get('location_notes')
        tips_for_attendees = request.form.get('tips_for_attendees')
        max_attendees = request.form.get('max_attendees')
        organizer_id = request.form.get('organizer_id')
        co_host_id = request.form.get('co_host_id', '')
        
        # Validate organizer
        if not organizer_id:
            flash('Please select a primary organizer.', 'error')
            return redirect(url_for('edit_event', event_id=event_id))
            
        try:
            organizer = User.get_by_id(organizer_id)
            if not organizer.can_organize_events():
                flash('Selected organizer does not have permission to organize events.', 'error')
                return redirect(url_for('edit_event', event_id=event_id))
        except User.DoesNotExist:
            flash('Selected organizer not found.', 'error')
            return redirect(url_for('edit_event', event_id=event_id))
        
        # Check permission: only admins or the original/new organizer can edit
        if not (current_user.role == 'admin' or current_user.id == event.organizer_id or current_user.id == organizer_id):
            flash('You can only edit events you organize unless you are an admin.', 'error')
            return redirect(url_for('edit_event', event_id=event_id))
        
        # Parse dates and times
        date = dt.strptime(date_str, '%Y-%m-%d')
        exact_time = dt.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
        
        # Validate Google Maps link if provided
        valid_maps_domains = ['maps.google.com', 'www.google.com/maps', 'maps.app.goo.gl', 'goo.gl/maps']
        if google_maps_link:
            is_valid_maps_link = any(domain in google_maps_link.lower() for domain in valid_maps_domains)
            if not is_valid_maps_link:
                flash('If provided, Google Maps link must be from Google Maps (maps.google.com, www.google.com/maps, or maps.app.goo.gl).', 'error')
                return redirect(url_for('edit_event', event_id=event_id))
        
        # Handle co-host
        co_host = None
        if co_host_id:
            try:
                co_host = User.get_by_id(co_host_id)
                if not co_host.can_organize_events():
                    flash('Co-host must be an organizer.', 'error')
                    return redirect(url_for('edit_event', event_id=event_id))
            except User.DoesNotExist:
                flash('Co-host not found.', 'error')
                return redirect(url_for('edit_event', event_id=event_id))
        
        # Handle event note
        event_note_id = request.form.get('event_note_id')
        event_note = None
        if event_note_id:
            try:
                from cosypolyamory.models.event_note import EventNote
                event_note = EventNote.get_by_id(event_note_id)
            except EventNote.DoesNotExist:
                flash('Selected event note not found.', 'error')
                return redirect(url_for('edit_event', event_id=event_id))

        # Update event
        event.title = title
        event.description = description
        event.barrio = barrio
        event.time_period = time_period
        event.date = date
        event.establishment_name = establishment_name
        event.google_maps_link = google_maps_link
        event.location_notes = location_notes or None
        event.exact_time = exact_time
        event.organizer = organizer
        event.co_host = co_host
        event.tips_for_attendees = tips_for_attendees.strip() if tips_for_attendees and tips_for_attendees.strip() else None
        event.max_attendees = int(max_attendees) if max_attendees else None
        event.event_note = event_note
        event.save()
        
        flash(f'Event "{title}" has been updated successfully!', 'success')
        return redirect(url_for('event_detail', event_id=event.id))
        
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events_list'))
    except ValueError as e:
        flash(f'Error updating event: {str(e)}', 'error')
        return redirect(url_for('edit_event', event_id=event_id))
    except Exception as e:
        flash(f'Unexpected error: {str(e)}', 'error')
        return redirect(url_for('edit_event', event_id=event_id))

@app.route('/events/<int:event_id>/rsvp', methods=['POST'])
@approved_user_required
def rsvp_event(event_id):
    """RSVP to an event"""
    try:
        event = Event.get_by_id(event_id)
        status = request.form.get('status')
        notes = request.form.get('notes', '')
        
        # Handle RSVP cancellation (empty status)
        if status == '' or status is None:
            try:
                rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == current_user))
                rsvp.delete_instance()
                message = 'Attendance cancelled'
                if request.headers.get('Accept') == 'application/json':
                    return jsonify({'success': True, 'message': message, 'status': None})
                flash(message, 'success')
            except RSVP.DoesNotExist:
                message = 'No attendance record found to cancel.'
                if request.headers.get('Accept') == 'application/json':
                    return jsonify({'success': False, 'message': message})
                flash(message, 'info')
            return redirect(url_for('event_detail', event_id=event_id))
        
        if status not in ['yes', 'no', 'maybe']:
            message = 'Invalid attendance status.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # Update or create RSVP
        try:
            rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == current_user))
            rsvp.status = status
            rsvp.notes = notes
            rsvp.updated_at = datetime.now()
            rsvp.save()
            status_text = 'Going' if status == 'yes' else 'Not Going' if status == 'no' else 'Maybe'
            message = f'Attendance confirmed: {status_text}'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': True, 'message': message, 'status': status})
            flash(message, 'success')
        except RSVP.DoesNotExist:
            RSVP.create(
                event=event,
                user=current_user,
                status=status,
                notes=notes
            )
            status_text = 'Going' if status == 'yes' else 'Not Going' if status == 'no' else 'Maybe'
            message = f'Attendance confirmed: {status_text}'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': True, 'message': message, 'status': status})
            flash(message, 'success')
        
        return redirect(url_for('event_detail', event_id=event_id))
        
    except Event.DoesNotExist:
        message = 'Event not found.'
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('events_list'))

@app.route('/admin')
@admin_or_organizer_required
def admin():
    """Admin dashboard"""
    users = list(User.select())
    return render_template('admin/admin.html', users=users)


# Event Notes Admin Routes (admins and organizers only)
from cosypolyamory.models.event_note import EventNote

@app.route('/admin/event-notes')
@admin_or_organizer_required
def event_notes():
    notes = EventNote.select().order_by(EventNote.name)
    return render_template('events/event_notes.html', event_notes=notes)

@app.route('/admin/event-notes/add', methods=['GET', 'POST'])
@admin_or_organizer_required
def add_event_note():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        note = request.form.get('note', '').strip()
        if not name or not note:
            flash('Both name and note are required.', 'error')
            return render_template('events/add_event_note.html')
        # Check for duplicate name
        if EventNote.select().where(EventNote.name == name).exists():
            flash('A note with this name already exists.', 'error')
            return render_template('events/add_event_note.html')
        EventNote.create(name=name, note=note)
        flash('Event note added successfully.', 'success')
        return redirect(url_for('event_notes'))
    return render_template('events/add_event_note.html')

@app.route('/admin/event-notes/<int:note_id>/edit', methods=['GET', 'POST'])
@admin_or_organizer_required
def edit_event_note(note_id):
    try:
        note = EventNote.get_by_id(note_id)
    except EventNote.DoesNotExist:
        flash('Event note not found.', 'error')
        return redirect(url_for('event_notes'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        note_text = request.form.get('note', '').strip()
        if not name or not note_text:
            flash('Both name and note are required.', 'error')
            return render_template('events/edit_event_note.html', note=note)
        # Check for duplicate name (excluding self)
        if EventNote.select().where((EventNote.name == name) & (EventNote.id != note.id)).exists():
            flash('A note with this name already exists.', 'error')
            return render_template('events/edit_event_note.html', note=note)
        note.name = name
        note.note = note_text
        note.save()
        flash('Event note updated successfully.', 'success')
        return redirect(url_for('event_notes'))
    return render_template('events/edit_event_note.html', note=note)

# Register additional API routes
import cosypolyamory.api_admin_application
import cosypolyamory.api_admin_application_by_user
import cosypolyamory.api_admin_application_review

# Register route blueprints
from cosypolyamory.routes import register_routes
register_routes(app)

