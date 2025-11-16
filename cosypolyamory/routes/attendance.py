"""
Attendance/RSVP routes for cosypolyamory.org

Handles RSVP functionality and attendance management.
"""

import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user

from cosypolyamory.models.user import User
from cosypolyamory.models.event import Event
from cosypolyamory.models.rsvp import RSVP
from cosypolyamory.models.event_note import EventNote
from cosypolyamory.models.no_show import NoShow
from cosypolyamory.database import database
from cosypolyamory.decorators import organizer_required, approved_user_required
from cosypolyamory.notification import send_notification_email, send_rsvp_confirmation, notify_event_updated, notify_event_cancelled, notify_host_assigned, notify_host_removed, send_waitlist_promotion_notification, send_rsvp_update_notification

bp = Blueprint('attendance', __name__, url_prefix='/events')


def organizer_required(f):
    """Decorator to require organizer access"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.can_organize_events():
            flash('Organizer access required.', 'error')
            return redirect(url_for('pages.index'))
        return f(*args, **kwargs)

    return decorated_function


def approved_user_required(f):
    """Decorator to require approved user status"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role not in ['approved', 'admin', 'organizer']:
            message = 'Community approval required to access this feature.'
            if current_user.role == 'pending':
                message = 'Your application is pending review. You\'ll receive access once approved.'
            elif current_user.role == 'rejected':
                message = 'Your application was not approved for community access.'
            flash(message, 'warning')
            return redirect(url_for('pages.index'))
        return f(*args, **kwargs)

    return decorated_function



# Manage attendance API:
# This is the ONLY endpoint that should modify event attendance/RSVPs.
# 
# This API endpoint takes a POST'ed JSON doc with the following fields:
# - attendance_yes: list of (user_id, notify) tuples - users attending (FCFS order)
# - attendance_no: list of (user_id, notify) tuples - users not attending
# - attendance_maybe: list of (user_id, notify) tuples - users with maybe status
# - attendance_waitlist: list of (user_id, notify) tuples - users on waitlist
# - remove_attendance: list of (user_id, notify) tuples - completely remove RSVPs from event
#
# Each tuple contains (user_id, notify) where user_id is a string (e.g., 'google_123456',
# 'test_user_003') and notify is a boolean indicating whether to send notification emails
# for this change. Plain user_id strings are also accepted and will default to notify=True.
#
# Permission model:
#   - Organizers and admins can manage all attendees
#   - Approved members can only manage their own attendance
#
# Transaction-safe processing order:
#   Step 0: Remove RSVPs (remove_attendance list)
#   Step 1: Apply attendance_no updates (clear spots)
#   Step 2: Apply attendance_yes updates (auto-waitlist if full)
#   Step 3: Apply attendance_maybe updates
#   Step 4: Apply attendance_waitlist updates (explicit waitlist)
#   Step 5: Validate capacity constraints
#   Step 6: Ensure host/co-host have 'yes' RSVPs (always enforced)
#   Step 7: Promote waitlisted users FCFS if capacity available
#   Step 8: Final capacity validation
#   
# All changes are wrapped in database.atomic() transaction - any capacity violation
# triggers automatic rollback. Notifications are sent AFTER successful commit.
#
# Auto-waitlist behavior: Users RSVPing 'yes' to full events are automatically moved
# to waitlist status instead, except for existing 'yes' attendees.
#
# Notification types:
#   - New 'yes' RSVP: send_rsvp_confirmation
#   - Status change: send_rsvp_update_notification  
#   - Waitlist promotion: send_waitlist_promotion_notification
#   - RSVP removal: send_rsvp_update_notification with 'removed' status
#
# Returns JSON with success status, counts, and list of promoted users if applicable.

def process_attendance_changes(event_id, attendance_data, requesting_user_id=None, no_auto_promote=False):
    """
    Core function to process attendance changes for an event.
    
    This function can be called by other parts of the application to manage attendance.
    
    Args:
        event_id: The ID of the event
        attendance_data: Dict with keys:
            - attendance_yes: list of (user_id, notify) tuples or plain user IDs (strings)
            - attendance_no: list of (user_id, notify) tuples or plain user IDs (strings)
            - attendance_maybe: list of (user_id, notify) tuples or plain user IDs (strings)
            - attendance_waitlist: list of (user_id, notify) tuples or plain user IDs (strings)
            - remove_attendance: list of (user_id, notify) tuples or plain user IDs (strings)
        requesting_user_id: ID (string) of user making the request (for permission checks)
                           If None, admin privileges are assumed
        no_auto_promote: If True, skip automatic host RSVP assignment and waitlist promotion
                        (default: False)
    
    Returns:
        Tuple of (success: bool, data: dict, status_code: int)
        - If success=True, data contains response with rsvp_count, waitlist_count, etc.
        - If success=False, data contains error message
    """
    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        return False, {'error': 'Event not found'}, 404
    
    # Check permissions based on user role
    if requesting_user_id:
        try:
            requesting_user = User.get_by_id(requesting_user_id)
            is_admin_or_organizer = (requesting_user.role in ['admin', 'organizer'] or 
                                      event.organizer_id == requesting_user_id or 
                                      (event.co_host and event.co_host_id == requesting_user_id))
        except User.DoesNotExist:
            return False, {'error': 'Requesting user not found'}, 404
    else:
        # No requesting user = assume admin privileges
        is_admin_or_organizer = True
        requesting_user = None
    
    attendance_yes = attendance_data.get('attendance_yes', [])
    attendance_no = attendance_data.get('attendance_no', [])
    attendance_maybe = attendance_data.get('attendance_maybe', [])
    attendance_waitlist = attendance_data.get('attendance_waitlist', [])
    remove_attendance = attendance_data.get('remove_attendance', [])
    
    # Parse tuples of (user_id, notify) or plain user_id
    def parse_attendance_list(items):
        """Convert list of (user_id, notify) tuples or plain user_ids to [(user_id, notify)]"""
        result = []
        for item in items:
            try:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    # Tuple format: (user_id, notify)
                    user_id = str(item[0])  # User IDs are strings in this system
                    notify = bool(item[1])
                    result.append((user_id, notify))
                elif isinstance(item, (list, tuple)) and len(item) == 1:
                    # Single-element tuple: (user_id,) - default notify to True
                    user_id = str(item[0])
                    result.append((user_id, True))
                else:
                    # Plain user_id - default notify to True
                    user_id = str(item)
                    result.append((user_id, True))
            except (ValueError, TypeError) as e:
                # Provide more helpful error message
                raise ValueError(f"Invalid user ID format: {item!r}")
        return result
    
    # Validate and parse input
    try:
        attendance_yes = parse_attendance_list(attendance_yes)
        attendance_no = parse_attendance_list(attendance_no)
        attendance_maybe = parse_attendance_list(attendance_maybe)
        attendance_waitlist = parse_attendance_list(attendance_waitlist)
        # Parse remove_attendance - support both plain IDs and tuples with notify flag
        remove_attendance = parse_attendance_list(remove_attendance)
    except (ValueError, TypeError) as e:
        return False, {'error': f'Invalid user ID or notify format: {str(e)}'}, 400
    
    # If not admin/organizer, validate user can only change their own RSVP
    if not is_admin_or_organizer and requesting_user_id:
        all_user_ids = set([uid for uid, _ in attendance_yes + attendance_no + attendance_maybe + attendance_waitlist + remove_attendance])
        if len(all_user_ids) != 1 or requesting_user_id not in all_user_ids:
            return False, {'error': 'You can only manage your own attendance'}, 403
    
    # Start transaction
    try:
        with database.atomic():
            # Track changes for notifications
            promoted_users = []
            updated_rsvps = []
            removed_users = []
            
            # Step 0: Remove RSVPs completely (before status updates)
            for user_id, notify in remove_attendance:
                try:
                    user = User.get_by_id(user_id)
                    try:
                        rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == user))
                        was_attending = rsvp.status == 'yes'
                        rsvp.delete_instance()
                        removed_users.append((user, was_attending, notify))
                    except RSVP.DoesNotExist:
                        # No RSVP to remove, continue
                        pass
                except User.DoesNotExist:
                    database.rollback()
                    return False, {'error': f'User {user_id} not found'}, 400
            
            # Step 1: Apply attendance_no updates first (add/update users to 'no' status)
            for user_id, notify in attendance_no:
                try:
                    user = User.get_by_id(user_id)
                    rsvp, created = RSVP.get_or_create(
                        event=event,
                        user=user,
                        defaults={'status': 'no', 'created_at': datetime.now(), 'updated_at': datetime.now()}
                    )
                    if created:
                        # New RSVP created
                        updated_rsvps.append({'user': user, 'old_status': None, 'new_status': 'no', 'notify': notify})
                    elif rsvp.status != 'no':
                        # Existing RSVP status changed
                        old_status = rsvp.status
                        rsvp.status = 'no'
                        rsvp.updated_at = datetime.now()
                        rsvp.save()
                        updated_rsvps.append({'user': user, 'old_status': old_status, 'new_status': 'no', 'notify': notify})
                except User.DoesNotExist:
                    database.rollback()
                    return False, {'error': f'User {user_id} not found'}, 400
            
            # Step 2: Apply attendance_yes updates (add/update users to 'yes' status)
            # If event is full, automatically add to waitlist instead
            for user_id, notify in attendance_yes:
                try:
                    user = User.get_by_id(user_id)
                    
                    # Check if event is full - if so, add to waitlist instead of 'yes'
                    current_yes_count = RSVP.select().where(
                        (RSVP.event == event) & (RSVP.status == 'yes')
                    ).count()
                    
                    desired_status = 'yes'
                    if event.max_attendees and current_yes_count >= event.max_attendees:
                        # Check if this user already has 'yes' status (don't demote them)
                        try:
                            existing = RSVP.get((RSVP.event == event) & (RSVP.user == user))
                            if existing.status != 'yes':
                                desired_status = 'waitlist'
                        except RSVP.DoesNotExist:
                            desired_status = 'waitlist'
                    
                    rsvp, created = RSVP.get_or_create(
                        event=event,
                        user=user,
                        defaults={'status': desired_status, 'created_at': datetime.now(), 'updated_at': datetime.now()}
                    )
                    if created:
                        # New RSVP created
                        updated_rsvps.append({'user': user, 'old_status': None, 'new_status': desired_status, 'notify': notify})
                    elif rsvp.status != desired_status:
                        # Existing RSVP status changed
                        old_status = rsvp.status
                        rsvp.status = desired_status
                        rsvp.updated_at = datetime.now()
                        rsvp.save()
                        updated_rsvps.append({'user': user, 'old_status': old_status, 'new_status': desired_status, 'notify': notify})
                except User.DoesNotExist:
                    database.rollback()
                    return False, {'error': f'User {user_id} not found'}, 400
            
            # Step 3: Apply attendance_maybe updates (add/update users to 'maybe' status)
            for user_id, notify in attendance_maybe:
                try:
                    user = User.get_by_id(user_id)
                    rsvp, created = RSVP.get_or_create(
                        event=event,
                        user=user,
                        defaults={'status': 'maybe', 'created_at': datetime.now(), 'updated_at': datetime.now()}
                    )
                    if created:
                        # New RSVP created
                        updated_rsvps.append({'user': user, 'old_status': None, 'new_status': 'maybe', 'notify': notify})
                    elif rsvp.status != 'maybe':
                        # Existing RSVP status changed
                        old_status = rsvp.status
                        rsvp.status = 'maybe'
                        rsvp.updated_at = datetime.now()
                        rsvp.save()
                        updated_rsvps.append({'user': user, 'old_status': old_status, 'new_status': 'maybe', 'notify': notify})
                except User.DoesNotExist:
                    database.rollback()
                    return False, {'error': f'User {user_id} not found'}, 400
            
            # Step 4: Apply attendance_waitlist updates (add/update users to 'waitlist' status)
            for user_id, notify in attendance_waitlist:
                try:
                    user = User.get_by_id(user_id)
                    rsvp, created = RSVP.get_or_create(
                        event=event,
                        user=user,
                        defaults={'status': 'waitlist', 'created_at': datetime.now(), 'updated_at': datetime.now()}
                    )
                    if created:
                        # New RSVP created
                        updated_rsvps.append({'user': user, 'old_status': None, 'new_status': 'waitlist', 'notify': notify})
                    elif rsvp.status != 'waitlist':
                        # Existing RSVP status changed
                        old_status = rsvp.status
                        rsvp.status = 'waitlist'
                        rsvp.updated_at = datetime.now()
                        rsvp.save()
                        updated_rsvps.append({'user': user, 'old_status': old_status, 'new_status': 'waitlist', 'notify': notify})
                except User.DoesNotExist:
                    database.rollback()
                    return False, {'error': f'User {user_id} not found'}, 400
            
            # Step 5: Check capacity 
            current_yes_count = RSVP.select().where(
                (RSVP.event == event) & (RSVP.status == 'yes')
            ).count()
            
            if event.max_attendees and current_yes_count > event.max_attendees:
                database.rollback()
                return False, {
                    'error': f'Cannot update attendance: would exceed event capacity ({current_yes_count} attending, max {event.max_attendees})'
                }, 400
            
            # Step 5: Ensure hosts have RSVPs and promote waitlist (skip if no_auto_promote is True)
            if not no_auto_promote:
                # Ensure organizer has 'yes' RSVP
                organizer_rsvp, created = RSVP.get_or_create(
                    event=event,
                    user=event.organizer,
                    defaults={'status': 'yes', 'created_at': datetime.now(), 'updated_at': datetime.now()}
                )
                if created:
                    # New host RSVP created - add to tracking with notify=False (hosts don't need their own confirmation)
                    updated_rsvps.append({'user': event.organizer, 'old_status': None, 'new_status': 'yes', 'notify': False})
                elif organizer_rsvp.status != 'yes':
                    # Existing RSVP status changed
                    old_status = organizer_rsvp.status
                    organizer_rsvp.status = 'yes'
                    organizer_rsvp.updated_at = datetime.now()
                    organizer_rsvp.save()
                    updated_rsvps.append({'user': event.organizer, 'old_status': old_status, 'new_status': 'yes', 'notify': False})
                
                # Ensure co-host has 'yes' RSVP if there is one
                if event.co_host:
                    cohost_rsvp, created = RSVP.get_or_create(
                        event=event,
                        user=event.co_host,
                        defaults={'status': 'yes', 'created_at': datetime.now(), 'updated_at': datetime.now()}
                    )
                    if created:
                        # New co-host RSVP created - add to tracking with notify=False
                        updated_rsvps.append({'user': event.co_host, 'old_status': None, 'new_status': 'yes', 'notify': False})
                    elif cohost_rsvp.status != 'yes':
                        # Existing RSVP status changed
                        old_status = cohost_rsvp.status
                        cohost_rsvp.status = 'yes'
                        cohost_rsvp.updated_at = datetime.now()
                        cohost_rsvp.save()
                        updated_rsvps.append({'user': event.co_host, 'old_status': old_status, 'new_status': 'yes', 'notify': False})
                
                # Recount after adding hosts
                current_yes_count = RSVP.select().where(
                    (RSVP.event == event) & (RSVP.status == 'yes')
                ).count()
                
                # Check capacity again after adding hosts
                if event.max_attendees and current_yes_count > event.max_attendees:
                    database.rollback()
                    return False, {
                        'error': f'Cannot update attendance: adding required host RSVPs would exceed event capacity ({current_yes_count} attending, max {event.max_attendees})'
                    }, 400
                
                # Promote waitlisted users if there's capacity
                if event.max_attendees:
                    available_spots = event.max_attendees - current_yes_count
                    if available_spots > 0:
                        waitlisted = RSVP.select().where(
                            (RSVP.event == event) & (RSVP.status == 'waitlist')
                        ).order_by(RSVP.created_at).limit(available_spots)
                        
                        for rsvp in waitlisted:
                            rsvp.status = 'yes'
                            rsvp.updated_at = datetime.now()
                            rsvp.save()
                            promoted_users.append(rsvp.user)
            
            # Final capacity check
            final_yes_count = RSVP.select().where(
                (RSVP.event == event) & (RSVP.status == 'yes')
            ).count()
            
            if event.max_attendees and final_yes_count > event.max_attendees:
                database.rollback()
                return False, {
                    'error': f'Cannot update attendance: final state would exceed event capacity ({final_yes_count} attending, max {event.max_attendees})'
                }, 400
        
        # Transaction committed successfully
        # Now send notifications for all status changes (after transaction is complete)
        # Only send notifications if the notify flag is True
        for rsvp_update in updated_rsvps:
            if rsvp_update['notify']:
                user = rsvp_update['user']
                old_status = rsvp_update['old_status']
                new_status = rsvp_update['new_status']
                try:
                    # Send appropriate notification based on status change
                    if new_status == 'yes' and old_status is None:
                        # New RSVP with 'yes' status - send confirmation email
                        rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == user))
                        send_rsvp_confirmation(user, event, rsvp)
                    elif new_status == 'yes' and old_status != 'yes':
                        # Existing RSVP changed to 'yes' - send update notification
                        send_rsvp_update_notification(user, event, new_status)
                    elif old_status and new_status != old_status:
                        # Any other status change - send update notification
                        send_rsvp_update_notification(user, event, new_status)
                except Exception as e:
                    current_app.logger.error(f"Failed to send RSVP notification to {user.email}: {e}")
        
        # Send waitlist promotion notifications (always notify on promotion)
        for user in promoted_users:
            try:
                send_waitlist_promotion_notification(user, event)
            except Exception as e:
                current_app.logger.error(f"Failed to send waitlist promotion notification to {user.email}: {e}")
        
        # Send removal notifications (only if notify flag is True)
        for user, was_attending, notify in removed_users:
            if notify:
                try:
                    send_rsvp_update_notification(user, event, 'removed')
                except Exception as e:
                    current_app.logger.error(f"Failed to send removal notification to {user.email}: {e}")
        
        response_data = {
            'success': True,
            'message': 'Attendance updated successfully',
            'rsvp_count': RSVP.select().where(
                (RSVP.event == event) & (RSVP.status == 'yes')
            ).count(),
            'waitlist_count': RSVP.select().where(
                (RSVP.event == event) & (RSVP.status == 'waitlist')
            ).count()
        }
        
        # Include requesting user's status if they were affected
        if requesting_user_id:
            try:
                user_rsvp = RSVP.get((RSVP.event == event) & (RSVP.user_id == requesting_user_id))
                response_data['user_status'] = user_rsvp.status
            except RSVP.DoesNotExist:
                response_data['user_status'] = None
        
        if promoted_users:
            response_data['promoted_count'] = len(promoted_users)
            response_data['promoted_users'] = [{'id': u.id, 'name': u.name} for u in promoted_users]
        
        if updated_rsvps:
            response_data['updated_count'] = len(updated_rsvps)
        
        if removed_users:
            response_data['removed_count'] = len(removed_users)
        
        return True, response_data, 200
        
    except Exception as e:
        current_app.logger.error(f"Error managing attendance for event {event_id}: {str(e)}", exc_info=True)
        return False, {'error': 'An unexpected error occurred'}, 500


@bp.route('/<int:event_id>/manage_attendance', methods=['POST'])
@login_required
def manage_attendance(event_id):
    """
    API endpoint to manage event attendance.
    
    Expects JSON with:
    - attendance_yes: list of (user_id, notify) tuples or plain user IDs (strings)
    - attendance_no: list of (user_id, notify) tuples or plain user IDs (strings)
    - attendance_maybe: list of (user_id, notify) tuples or plain user IDs (strings)
    - attendance_waitlist: list of (user_id, notify) tuples or plain user IDs (strings)
    - remove_attendance: list of (user_id, notify) tuples or plain user IDs (strings)
    - no_auto_promote: optional boolean to skip automatic host RSVPs and waitlist promotion
    
    Returns JSON with success status and any relevant messages.
    """
    # Parse JSON request
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400
    
    # Extract no_auto_promote flag from data
    no_auto_promote = data.get('no_auto_promote', False)
    
    # Call the core processing function
    success, response_data, status_code = process_attendance_changes(
        event_id, 
        data, 
        requesting_user_id=current_user.id,
        no_auto_promote=no_auto_promote
    )
    
    # Convert to JSON response
    if not success:
        return jsonify({'success': False, **response_data}), status_code
    else:
        return jsonify({'success': True, **response_data}), status_code


@bp.route('/<int:event_id>/admin/attendance')
@approved_user_required
def edit_attendance(event_id):
    """Edit attendance page for admins/organizers"""
    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events.events_list'))

    # Check if user can edit attendance
    if not (current_user.role in ['admin', 'organizer'] or event.organizer_id == current_user.id):
        flash('Access denied. Only admins, organizers, and event creators can edit attendance.', 'error')
        return redirect(url_for('events.event_detail', event_id=event_id))

    # Check if event is in the past - allow viewing but show info message
    from datetime import datetime
    current_time = datetime.now()
    event_has_passed = event.exact_time < current_time

    # Get all RSVPs
    rsvps_attending = list(RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).order_by(RSVP.created_at))

    rsvps_maybe = list(RSVP.select().where((RSVP.event == event) & (RSVP.status == 'maybe')).order_by(RSVP.created_at))

    rsvps_waitlist = list(RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(RSVP.created_at))

    rsvps_not_attending = list(RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).order_by(RSVP.created_at))

    # Calculate counts
    rsvp_count = len(rsvps_attending)
    maybe_count = len(rsvps_maybe)
    waitlist_count = len(rsvps_waitlist)
    not_attending_count = len(rsvps_not_attending)

    # Prepare host information for template
    organizer_id = event.organizer_id
    co_host_id = None
    if event.co_host:
        co_host_id = event.co_host.id
    
    # Check event timing for different permissions
    from datetime import datetime
    current_time = datetime.now()
    
    # Event has started (allow no-show marking)
    event_has_started = current_time >= event.exact_time
    
    # Event has completely passed (restrict attendance changes)
    event_end_time = event.end_time if event.end_time else event.exact_time
    event_has_passed = current_time > event_end_time

    # Get no-show data for this event
    no_shows = {}
    if event_has_started:  # Changed from event_has_passed to event_has_started
        # Get all no-show records for this event
        no_show_records = NoShow.select().where(NoShow.event == event)
        no_shows = {no_show.user.id: no_show for no_show in no_show_records}

    # Get total no-show counts for all users (for upcoming events only)
    user_no_show_counts = {}
    if not event_has_passed:
        # Collect all unique user IDs from RSVPs
        all_user_ids = set()
        for rsvp in rsvps_attending + rsvps_maybe + rsvps_waitlist + rsvps_not_attending:
            all_user_ids.add(rsvp.user.id)
        
        # Get no-show counts for each user
        for user_id in all_user_ids:
            count = NoShow.select().where(NoShow.user == user_id).count()
            if count > 0:
                user_no_show_counts[user_id] = count
                
    # Calculate pronoun statistics for attending users
    pronoun_stats = {'singular': {}, 'plural': {}}
    try:
        from cosypolyamory.models.user import User
        
        # Get users who are attending and have pronouns
        attending_user_ids = [rsvp.user.id for rsvp in rsvps_attending]
        attending_users = (User
                          .select()
                          .where(
                              (User.id.in_(attending_user_ids)) &
                              (User.pronouns.is_null(False))
                          ))
        
        # Count pronouns - parse combined format like "they/them", "she/her"
        # Extract first two words only for graphing (e.g., "they/them" from "they/them/theirs")
        pronoun_counts = {}
        
        for user in attending_users:
            if user.pronouns:
                pronouns = user.pronouns.strip()
                # Split by slash and take only first two words
                parts = pronouns.split('/')
                if len(parts) >= 2:
                    # Use first two words for the graph
                    graph_pronouns = f"{parts[0]}/{parts[1]}"
                else:
                    # If only one word, use as-is (shouldn't happen with validation)
                    graph_pronouns = pronouns
                pronoun_counts[graph_pronouns] = pronoun_counts.get(graph_pronouns, 0) + 1
        
        pronoun_stats = {
            'pronouns': pronoun_counts
        }
        
    except Exception as e:
        print(f"Error calculating pronoun statistics: {e}")
        pronoun_stats = {'pronouns': {}}

    return render_template('events/edit_attendance.html',
                           event=event,
                           rsvps_attending=rsvps_attending,
                           rsvps_maybe=rsvps_maybe,
                           rsvps_waitlist=rsvps_waitlist,
                           rsvps_not_attending=rsvps_not_attending,
                           rsvp_count=rsvp_count,
                           maybe_count=maybe_count,
                           waitlist_count=waitlist_count,
                           not_attending_count=not_attending_count,
                           organizer_id=organizer_id,
                           co_host_id=co_host_id,
                           event_has_started=event_has_started,
                           event_has_passed=event_has_passed,
                           no_shows=no_shows,
                           user_no_show_counts=user_no_show_counts,
                           pronoun_stats=pronoun_stats,
                           now=current_time)