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
# This API end point takes a POST'ed JSON doc with the following fields:
# - Attendance yes: ordered list of tuple(user, notify) (first come first serve)
# - Attendance no: ordered list of tuple(user, notify).
# - Attendance maybe: ordered list of tuple(user, notify).
# - remove_attendance: list of user_ids to completely remove RSVPs from
# Use the current user's role to sanity check the request
#   - organizers and admins can carry out all actions.
#   - approved members can only act on their own behalf.
# 
#  - Update the attendance list by first applying the attendance no's, and then the attendance yes's. Then apply maybes.
#  - If the additions would make the event go over capacity (adding a co-host for example), reject all, abort the DB transaction
#    set an informative flash message. If a user say attendance yes, when the event is full, add them to the waitlist instead.
#  - ensure that the host and optional co-host has an attendance yes. If not, add them.
#  - if the event is not at capacity and people are on the waitlist, promote the waitlisted people, first come first serve until the event is full.
#  - If the above make the event go over capacity, reject, abort DB, send flash.
#  - If all is within limits, commit the transaction.
#  - Send notifications according to the actions that where just taken. If a user rsvp'ed for the first time, send a rsvp confirmation email. otherwise send an RSVP change email.
#
# Features that we do not want to support anymore:
#  - RSVP notes.
#  - Host prevention logic. Automatically adding them replaces this feature
#  - Return HTML from back end. Will refactor front end.
#  - Remove all waitlist promotion logic in the front end.

@bp.route('/<int:event_id>/manage_attendance', methods=['POST'])
@login_required
def manage_attendance(event_id):
    """
    API endpoint to manage event attendance.
    
    Expects JSON with:
    - attendance_yes: list of user IDs who are attending
    - attendance_no: list of user IDs who are not attending
    - attendance_maybe: list of user IDs with maybe status
    
    Returns JSON with success status and any relevant messages.
    """
    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        return jsonify({'success': False, 'error': 'Event not found'}), 404
    
    # Check permissions based on user role
    is_admin_or_organizer = (current_user.role in ['admin', 'organizer'] or 
                              event.organizer_id == current_user.id or 
                              (event.co_host and event.co_host_id == current_user.id))
    
    # Parse JSON request
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400
    
    attendance_yes = data.get('attendance_yes', [])
    attendance_no = data.get('attendance_no', [])
    attendance_maybe = data.get('attendance_maybe', [])
    remove_attendance = data.get('remove_attendance', [])
    
    # Parse tuples of (user_id, notify) or plain user_id
    def parse_attendance_list(items):
        """Convert list of (user_id, notify) tuples or plain user_ids to [(user_id, notify)]"""
        result = []
        for item in items:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                # Tuple format: (user_id, notify)
                result.append((int(item[0]), bool(item[1])))
            elif isinstance(item, (list, tuple)) and len(item) == 1:
                # Single-element tuple: (user_id,) - default notify to True
                result.append((int(item[0]), True))
            else:
                # Plain user_id - default notify to True
                result.append((int(item), True))
        return result
    
    # Validate and parse input
    try:
        attendance_yes = parse_attendance_list(attendance_yes)
        attendance_no = parse_attendance_list(attendance_no)
        attendance_maybe = parse_attendance_list(attendance_maybe)
        # Parse remove_attendance as plain list of user IDs
        remove_attendance = [int(uid) for uid in remove_attendance]
    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': f'Invalid user ID or notify format: {str(e)}'}), 400
    
    # If not admin/organizer, validate user can only change their own RSVP
    if not is_admin_or_organizer:
        all_user_ids = set([uid for uid, _ in attendance_yes + attendance_no + attendance_maybe] + remove_attendance)
        if len(all_user_ids) != 1 or current_user.id not in all_user_ids:
            return jsonify({'success': False, 'error': 'You can only manage your own attendance'}), 403
    
    # Start transaction
    try:
        with database.atomic():
            # Track changes for notifications
            promoted_users = []
            updated_rsvps = []
            removed_users = []
            
            # Step 0: Remove RSVPs completely (before status updates)
            for user_id in remove_attendance:
                try:
                    user = User.get_by_id(user_id)
                    try:
                        rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == user))
                        was_attending = rsvp.status == 'yes'
                        rsvp.delete_instance()
                        removed_users.append((user, was_attending))
                    except RSVP.DoesNotExist:
                        # No RSVP to remove, continue
                        pass
                except User.DoesNotExist:
                    database.rollback()
                    return jsonify({'success': False, 'error': f'User {user_id} not found'}), 400
            
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
                    return jsonify({'success': False, 'error': f'User {user_id} not found'}), 400
            
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
                    return jsonify({'success': False, 'error': f'User {user_id} not found'}), 400
            
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
                    return jsonify({'success': False, 'error': f'User {user_id} not found'}), 400
            
            # Step 4: Check capacity 
            current_yes_count = RSVP.select().where(
                (RSVP.event == event) & (RSVP.status == 'yes')
            ).count()
            
            if event.max_attendees and current_yes_count > event.max_attendees:
                database.rollback()
                return jsonify({
                    'success': False, 
                    'error': f'Cannot update attendance: would exceed event capacity ({current_yes_count} attending, max {event.max_attendees})'
                }), 400
            
            # Step 5: Ensure hosts have RSVPs and promote waitlist (always done per updated spec)
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
                return jsonify({
                    'success': False, 
                    'error': f'Cannot update attendance: adding required host RSVPs would exceed event capacity ({current_yes_count} attending, max {event.max_attendees})'
                }), 400
            
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
                return jsonify({
                    'success': False, 
                    'error': f'Cannot update attendance: final state would exceed event capacity ({final_yes_count} attending, max {event.max_attendees})'
                }), 400
        
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
        
        # Send removal notifications (always notify on removal)
        for user, was_attending in removed_users:
            try:
                send_rsvp_update_notification(user, event, 'removed')
            except Exception as e:
                current_app.logger.error(f"Failed to send removal notification to {user.email}: {e}")
        
        response_data = {
            'success': True,
            'message': 'Attendance updated successfully',
            'current_attending': RSVP.select().where(
                (RSVP.event == event) & (RSVP.status == 'yes')
            ).count()
        }
        
        if promoted_users:
            response_data['promoted_count'] = len(promoted_users)
            response_data['promoted_users'] = [{'id': u.id, 'name': u.name} for u in promoted_users]
        
        if updated_rsvps:
            response_data['updated_count'] = len(updated_rsvps)
        
        if removed_users:
            response_data['removed_count'] = len(removed_users)
        
        return jsonify(response_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Error managing attendance for event {event_id}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500


@bp.route('/<int:event_id>/rsvp', methods=['POST'])
@approved_user_required
def rsvp_event(event_id):
    """RSVP to an event"""
    from flask import jsonify

    try:
        event = Event.get_by_id(event_id)

        # Prevent hosts and co-hosts from RSVPing to their own events
        if current_user.id == event.organizer_id or (event.co_host and current_user.id == event.co_host.id):
            message = 'Hosts and co-hosts cannot RSVP to their own events.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message}), 403
            flash(message, 'error')
            return redirect(url_for('events.event_detail', event_id=event_id))

        status = request.form.get('status')
        notes = request.form.get('notes', '')

        # Handle RSVP cancellation (empty status)
        if status == '' or status is None:
            try:
                with database.atomic():
                    rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == current_user))
                    was_attending = rsvp.status == 'yes'
                    rsvp.delete_instance()

                    # If user was attending and event has capacity, promote next waitlisted user
                    promoted_user = None
                    if was_attending and event.max_attendees:
                        next_waitlisted = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(
                            RSVP.created_at).first()
                        if next_waitlisted:
                            next_waitlisted.status = 'yes'
                            next_waitlisted.updated_at = datetime.now()
                            next_waitlisted.save()
                            promoted_user = next_waitlisted.user.name
                            # Send notification to promoted user
                            send_waitlist_promotion_notification(next_waitlisted.user, event)

                message = 'Attendance cancelled'
                if promoted_user:
                    message += f'. {promoted_user} has been moved from waitlist to attending.'

                if request.headers.get('Accept') == 'application/json':
                    # Recalculate lists and counts
                    rsvp_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
                    rsvp_no_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).count()
                    rsvps = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).order_by(RSVP.created_at)
                    rsvps_no = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).order_by(RSVP.created_at)
                    rsvps_maybe = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'maybe')).order_by(RSVP.created_at)
                    rsvps_waitlist = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(
                        RSVP.created_at)
                    
                    # Create consolidated attendance list 
                    all_rsvps = list(rsvps) + list(rsvps_no) + list(rsvps_maybe) + list(rsvps_waitlist)
                    
                    # Create mock RSVP objects for host/co-host display
                    class MockRSVP:
                        def __init__(self, user, status):
                            self.user = user
                            self.status = status
                            self.created_at = event.created_at
                    
                    # Remove host and co-host from regular RSVP lists if they exist
                    all_rsvps = [rsvp for rsvp in all_rsvps if rsvp.user.id != event.organizer_id]
                    if event.co_host:
                        all_rsvps = [rsvp for rsvp in all_rsvps if rsvp.user.id != event.co_host.id]
                    
                    # Always add host and co-host at the beginning with their special status
                    all_rsvps.append(MockRSVP(event.organizer, 'host'))
                    if event.co_host:
                        all_rsvps.append(MockRSVP(event.co_host, 'co-host'))
                    
                    # Sort by status priority, then by first name, then by last name
                    status_priority = {'yes': 0, 'maybe': 1, 'waitlist': 2, 'no': 3, 'co-host': 4, 'host': 5}
                    
                    def sort_key(rsvp):
                        # Split the name to get first and last name
                        name_parts = rsvp.user.name.split()
                        first_name = name_parts[0] if name_parts else ''
                        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                        return (status_priority.get(rsvp.status, 6), first_name.lower(), last_name.lower())
                    
                    consolidated_attendance = sorted(all_rsvps, key=sort_key)
                    
                    from flask import render_template
                    attendees_html = render_template('events/event_detail_attendees.html', rsvps=rsvps)
                    not_attending_html = render_template('events/event_detail_not_attending.html', rsvps_no=rsvps_no)
                    waitlist_html = render_template('events/event_detail_waitlist.html', rsvps_waitlist=rsvps_waitlist)
                    consolidated_attendance_html = render_template('events/_consolidated_attendance.html', 
                                                                 consolidated_attendance=consolidated_attendance)
                    capacity_pills_html = render_template('events/_capacity_pills.html',
                                                          rsvp_count=rsvp_count,
                                                          event=event,
                                                          rsvps_waitlist=rsvps_waitlist)
                    header_pills_html = render_template('events/_header_pills.html',
                                                        rsvp_count=rsvp_count,
                                                        event=event,
                                                        rsvps_waitlist=rsvps_waitlist,
                                                        now=datetime.now())
                    return jsonify({
                        'success': True,
                        'message': message,
                        'status': None,
                        'user_rsvp': None,
                        'rsvp_count': rsvp_count,
                        'rsvp_no_count': rsvp_no_count,
                        'rsvps_html': attendees_html,
                        'rsvps_no_html': not_attending_html,
                        'waitlist_html': waitlist_html,
                        'consolidated_attendance_html': consolidated_attendance_html,
                        'capacity_pills_html': capacity_pills_html,
                        'header_pills_html': header_pills_html,
                        'promoted_user': promoted_user
                    })
                flash(message, 'success')
            except RSVP.DoesNotExist:
                message = 'No attendance record found to cancel.'
                if request.headers.get('Accept') == 'application/json':
                    return jsonify({'success': False, 'message': message})
                flash(message, 'info')
            return redirect(url_for('events.event_detail', event_id=event_id))

        if status not in ['yes', 'no', 'maybe']:
            message = 'Invalid attendance status.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
            return redirect(url_for('events.event_detail', event_id=event_id))
            return redirect(url_for('events.event_detail', event_id=event_id))

        # Enforce event capacity and waitlist
        from peewee import fn
        rsvp_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
        # If user is already RSVP'd, update their status
        try:
            with database.atomic():
                rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == current_user))
                prev_status = rsvp.status
                if status == 'yes':
                    if event.max_attendees and rsvp_count >= event.max_attendees and prev_status != 'yes':
                        rsvp.status = 'waitlist'
                        message = 'Event is full. You have been added to the waitlist.'
                    else:
                        rsvp.status = 'yes'
                        message = 'Attendance confirmed: Going'
                elif status == 'no':
                    rsvp.status = 'no'
                    message = 'Attendance confirmed: Not Going'
                elif status == 'maybe':
                    rsvp.status = 'maybe'
                    message = 'Attendance confirmed: Maybe'
                rsvp.notes = notes
                rsvp.updated_at = datetime.now()
                rsvp.save()

                # Automatic waitlist promotion when user changes from attending to not attending
                promoted_user = None
                if prev_status == 'yes' and rsvp.status != 'yes' and event.max_attendees:
                    yes_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
                    if yes_count < event.max_attendees:
                        next_waitlisted = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(
                            RSVP.created_at).first()
                        if next_waitlisted:
                            next_waitlisted.status = 'yes'
                            next_waitlisted.updated_at = datetime.now()
                            next_waitlisted.save()
                            promoted_user = next_waitlisted.user.name
                            # Send notification to promoted user
                            send_waitlist_promotion_notification(next_waitlisted.user, event)
                            message += f' {promoted_user} has been moved from waitlist to attending.'
        except RSVP.DoesNotExist:
            # New RSVP
            with database.atomic():
                if status == 'yes' and event.max_attendees and rsvp_count >= event.max_attendees:
                    rsvp = RSVP.create(event=event, user=current_user, status='waitlist', notes=notes)
                    message = 'Event is full. You have been added to the waitlist.'
                else:
                    rsvp = RSVP.create(event=event, user=current_user, status=status, notes=notes)
                    status_text = 'Going' if status == 'yes' else 'Not Going' if status == 'no' else 'Maybe'
                    message = f'Attendance confirmed: {status_text}'

        # Prepare response
        rsvp_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
        rsvp_no_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).count()
        rsvps = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).order_by(RSVP.created_at)
        rsvps_no = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).order_by(RSVP.created_at)
        rsvps_maybe = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'maybe')).order_by(RSVP.created_at)
        rsvps_waitlist = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(RSVP.created_at)
        
        # Create consolidated attendance list sorted by status priority, then by name
        all_rsvps = list(rsvps) + list(rsvps_no) + list(rsvps_maybe) + list(rsvps_waitlist)
        
        # Create mock RSVP objects for host/co-host display
        class MockRSVP:
            def __init__(self, user, status):
                self.user = user
                self.status = status
                self.created_at = event.created_at
        
        # Remove host and co-host from regular RSVP lists if they exist
        all_rsvps = [rsvp for rsvp in all_rsvps if rsvp.user.id != event.organizer_id]
        if event.co_host:
            all_rsvps = [rsvp for rsvp in all_rsvps if rsvp.user.id != event.co_host.id]
        
        # Always add host and co-host at the beginning with their special status
        all_rsvps.append(MockRSVP(event.organizer, 'host'))
        if event.co_host:
            all_rsvps.append(MockRSVP(event.co_host, 'co-host'))
        
        # Sort by status priority, then by first name, then by last name
        status_priority = {'yes': 0, 'maybe': 1, 'waitlist': 2, 'no': 3, 'co-host': 4, 'host': 5}
        
        def sort_key(rsvp):
            # Split the name to get first and last name
            name_parts = rsvp.user.name.split()
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            return (status_priority.get(rsvp.status, 6), first_name.lower(), last_name.lower())
        
        consolidated_attendance = sorted(all_rsvps, key=sort_key)
        
        from flask import render_template
        attendees_html = render_template('events/event_detail_attendees.html', rsvps=rsvps)
        not_attending_html = render_template('events/event_detail_not_attending.html', rsvps_no=rsvps_no)
        waitlist_html = render_template('events/event_detail_waitlist.html', rsvps_waitlist=rsvps_waitlist)
        consolidated_attendance_html = render_template('events/_consolidated_attendance.html', 
                                                     consolidated_attendance=consolidated_attendance)
        capacity_pills_html = render_template('events/_capacity_pills.html',
                                              rsvp_count=rsvp_count,
                                              event=event,
                                              rsvps_waitlist=rsvps_waitlist)
        header_pills_html = render_template('events/_header_pills.html',
                                            rsvp_count=rsvp_count,
                                            event=event,
                                            rsvps_waitlist=rsvps_waitlist,
                                            now=datetime.now())
        user_rsvp = {'status': rsvp.status} if rsvp else None
        if request.headers.get('Accept') == 'application/json':
            response_data = {
                'success': True,
                'message': message,
                'status': rsvp.status,
                'user_rsvp': user_rsvp,
                'rsvp_count': rsvp_count,
                'rsvp_no_count': rsvp_no_count,
                'waitlist_count': rsvps_waitlist.count() if hasattr(rsvps_waitlist, 'count') else len(rsvps_waitlist),
                'rsvps_html': attendees_html,
                'rsvps_no_html': not_attending_html,
                'waitlist_html': waitlist_html,
                'consolidated_attendance_html': consolidated_attendance_html,
                'total_attendance_count': len(consolidated_attendance),
                'capacity_pills_html': capacity_pills_html,
                'header_pills_html': header_pills_html
            }
            # Add promoted user info if someone was promoted
            if 'promoted_user' in locals() and promoted_user:
                response_data['promoted_user'] = promoted_user

            if status == 'yes':
                # Send RSVP confirmation email
                send_rsvp_confirmation(current_user, event, rsvp)

            return jsonify(response_data)

        flash(message, 'success')

        return redirect(url_for('events.event_detail', event_id=event_id))

    except Event.DoesNotExist:
        message = 'Event not found.'
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('events.events_list'))


@bp.route('/<int:event_id>/admin/rsvp/<user_id>/remove', methods=['POST'])
@approved_user_required
def admin_remove_rsvp(event_id, user_id):
    """Remove a user's RSVP (admin/organizer only)"""
    from flask import jsonify

    try:
        event = Event.get_by_id(event_id)
        target_user = User.get_by_id(user_id)

        # Check permissions: admin, organizer, or event host
        if not (current_user.role == 'admin' or current_user.can_organize_events() or current_user.id == event.organizer_id):
            message = 'Permission denied. Only administrators, organizers, or event hosts can remove RSVPs.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
            return redirect(url_for('events.event_detail', event_id=event_id))

        # Find and remove the RSVP
        try:
            rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == target_user))
            prev_status = rsvp.status

            # Check if notifications should be skipped
            skip_notification = request.form.get('skip_notification', 'false').lower() == 'true'

            rsvp.delete_instance()

            # Send removal notification unless skipped
            if not skip_notification:
                send_rsvp_update_notification(target_user, event, 'removed')

            message = f'RSVP removed for {target_user.name}'

            if request.headers.get('Accept') == 'application/json':
                # Recalculate lists and counts for real-time update
                rsvp_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
                rsvp_no_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).count()
                rsvps = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).order_by(RSVP.created_at)
                rsvps_no = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).order_by(RSVP.created_at)
                rsvps_waitlist = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(RSVP.created_at)
                rsvps_maybe = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'maybe')).order_by(RSVP.created_at)

                from flask import render_template
                attendees_html = render_template('events/event_detail_attendees.html', rsvps=rsvps, event=event)
                not_attending_html = render_template('events/event_detail_not_attending.html', rsvps_no=rsvps_no, event=event)
                waitlist_html = render_template('events/event_detail_waitlist.html', rsvps_waitlist=rsvps_waitlist, event=event)
                maybe_html = render_template('events/event_detail_maybe.html', rsvps_maybe=rsvps_maybe, event=event)
                capacity_pills_html = render_template('events/_capacity_pills.html',
                                                      rsvp_count=rsvp_count,
                                                      event=event,
                                                      rsvps_waitlist=rsvps_waitlist)
                header_pills_html = render_template('events/_header_pills.html',
                                                    rsvp_count=rsvp_count,
                                                    event=event,
                                                    rsvps_waitlist=rsvps_waitlist,
                                                    now=datetime.now())

                return jsonify({
                    'success': True,
                    'message': message,
                    'rsvp_count': rsvp_count,
                    'rsvp_no_count': rsvp_no_count,
                    'waitlist_count': rsvps_waitlist.count() if hasattr(rsvps_waitlist, 'count') else len(rsvps_waitlist),
                    'maybe_count': rsvps_maybe.count() if hasattr(rsvps_maybe, 'count') else len(rsvps_maybe),
                    'rsvps_html': attendees_html,
                    'rsvps_no_html': not_attending_html,
                    'waitlist_html': waitlist_html,
                    'maybe_html': maybe_html,
                    'capacity_pills_html': capacity_pills_html,
                    'header_pills_html': header_pills_html
                })

            flash(message, 'success')
            return redirect(url_for('events.event_detail', event_id=event_id))

        except RSVP.DoesNotExist:
            message = f'No RSVP found for {target_user.name}'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'info')
            return redirect(url_for('events.event_detail', event_id=event_id))

    except Event.DoesNotExist:
        message = 'Event not found.'
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('events.events_list'))
    except User.DoesNotExist:
        message = 'User not found.'
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('events.event_detail', event_id=event_id))
    except Exception as e:
        message = f'Error removing RSVP: {str(e)}'
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('events.event_detail', event_id=event_id))


@bp.route('/<int:event_id>/admin/rsvp/<user_id>/move', methods=['POST'])
@approved_user_required
def admin_move_rsvp(event_id, user_id):
    """Move a user's RSVP to a different status (admin/organizer only)"""
    from flask import jsonify

    try:
        event = Event.get_by_id(event_id)
        target_user = User.get_by_id(user_id)
        new_status = request.form.get('status')

        # Check permissions: admin, organizer, or event host
        if not (current_user.role == 'admin' or current_user.can_organize_events() or current_user.id == event.organizer_id):
            message = 'Permission denied. Only administrators, organizers, or event hosts can move RSVPs.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
            return redirect(url_for('events.event_detail', event_id=event_id))

        # Validate status
        if new_status not in ['yes', 'no', 'maybe', 'waitlist']:
            message = 'Invalid status. Must be yes, no, maybe, or waitlist.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
            return redirect(url_for('events.event_detail', event_id=event_id))

        # Find and update the RSVP
        try:
            rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == target_user))
            prev_status = rsvp.status

            # Check current event capacity
            current_yes_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
            is_event_full = event.max_attendees and current_yes_count >= event.max_attendees

            # Allow organizers to move people to waitlist regardless of capacity status
            # (removed previous restriction that prevented waitlist moves when event not full)

            # Handle capacity constraints when moving to 'yes'
            if new_status == 'yes' and prev_status != 'yes':
                if is_event_full:
                    # Silently move to waitlist instead when event is full
                    new_status = 'waitlist'
                    message = f'{target_user.name} moved to waitlist (event is full).'
                else:
                    message = f'{target_user.name} moved to attending.'
            elif new_status == 'no':
                message = f'{target_user.name} moved to not attending.'
            elif new_status == 'maybe':
                message = f'{target_user.name} moved to maybe attending.'
            elif new_status == 'waitlist':
                message = f'{target_user.name} moved to waitlist.'
            else:
                message = f'{target_user.name} status updated.'

            rsvp.status = new_status
            rsvp.updated_at = datetime.now()
            rsvp.save()

            # Check if notifications should be skipped
            skip_notification = request.form.get('skip_notification', 'false').lower() == 'true'

            # Send status update notification unless skipped
            if not skip_notification:
                send_rsvp_update_notification(target_user, event, new_status)

            if request.headers.get('Accept') == 'application/json':
                # Recalculate lists and counts for real-time update
                rsvp_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
                rsvp_no_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).count()
                rsvps = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).order_by(RSVP.created_at)
                rsvps_no = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).order_by(RSVP.created_at)
                rsvps_waitlist = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(RSVP.created_at)
                rsvps_maybe = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'maybe')).order_by(RSVP.created_at)

                # Check if current user can manage RSVPs
                can_manage_rsvps = (current_user.role == 'admin' or current_user.can_organize_events()
                                    or current_user.id == event.organizer_id)

                from flask import render_template
                try:
                    attendees_html = render_template('events/event_detail_attendees.html',
                                                     rsvps=rsvps,
                                                     event=event,
                                                     can_manage_rsvps=can_manage_rsvps)
                    not_attending_html = render_template('events/event_detail_not_attending.html',
                                                         rsvps_no=rsvps_no,
                                                         event=event,
                                                         can_manage_rsvps=can_manage_rsvps)
                    waitlist_html = render_template('events/event_detail_waitlist.html',
                                                    rsvps_waitlist=rsvps_waitlist,
                                                    event=event,
                                                    can_manage_rsvps=can_manage_rsvps)
                    maybe_html = render_template('events/event_detail_maybe.html',
                                                 rsvps_maybe=rsvps_maybe,
                                                 event=event,
                                                 can_manage_rsvps=can_manage_rsvps)
                    capacity_pills_html = render_template('events/_capacity_pills.html',
                                                          rsvp_count=rsvp_count,
                                                          event=event,
                                                          rsvps_waitlist=rsvps_waitlist)
                    header_pills_html = render_template('events/_header_pills.html',
                                                        rsvp_count=rsvp_count,
                                                        event=event,
                                                        rsvps_waitlist=rsvps_waitlist,
                                                        now=datetime.now())

                    return jsonify({
                        'success': True,
                        'message': message,
                        'new_status': new_status,
                        'rsvp_count': rsvp_count,
                        'rsvp_no_count': rsvp_no_count,
                        'rsvp_waitlist_count': rsvps_waitlist.count(),
                        'waitlist_count': rsvps_waitlist.count(),
                        'maybe_count': rsvps_maybe.count(),
                        'rsvps_html': attendees_html,
                        'rsvps_no_html': not_attending_html,
                        'waitlist_html': waitlist_html,
                        'maybe_html': maybe_html,
                        'capacity_pills_html': capacity_pills_html,
                        'header_pills_html': header_pills_html
                    })
                except Exception as template_error:
                    # Fallback to simple response if template rendering fails
                    return jsonify({
                        'success': True,
                        'message': message,
                        'new_status': new_status,
                        'rsvp_count': rsvp_count,
                        'rsvp_no_count': rsvp_no_count,
                        'rsvp_waitlist_count': rsvps_waitlist.count(),
                        'template_error': str(template_error)
                    })

            flash(message, 'success')
            return redirect(url_for('events.event_detail', event_id=event_id))

        except RSVP.DoesNotExist:
            message = f'No RSVP found for {target_user.name}'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'info')
            return redirect(url_for('events.event_detail', event_id=event_id))

    except Event.DoesNotExist:
        message = 'Event not found.'
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('events.events_list'))
    except User.DoesNotExist:
        message = 'User not found.'
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('events.event_detail', event_id=event_id))
    except Exception as e:
        message = f'Error moving RSVP: {str(e)}'
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('events.event_detail', event_id=event_id))


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