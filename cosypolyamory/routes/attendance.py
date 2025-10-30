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
                    rsvps_waitlist = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(
                        RSVP.created_at)
                    from flask import render_template
                    attendees_html = render_template('events/event_detail_attendees.html', rsvps=rsvps)
                    not_attending_html = render_template('events/event_detail_not_attending.html', rsvps_no=rsvps_no)
                    waitlist_html = render_template('events/event_detail_waitlist.html', rsvps_waitlist=rsvps_waitlist)
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
        rsvps_waitlist = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(RSVP.created_at)
        from flask import render_template
        attendees_html = render_template('events/event_detail_attendees.html', rsvps=rsvps)
        not_attending_html = render_template('events/event_detail_not_attending.html', rsvps_no=rsvps_no)
        waitlist_html = render_template('events/event_detail_waitlist.html', rsvps_waitlist=rsvps_waitlist)
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
                    message = f'Cannot move to attending: Event is full. {target_user.name} should be moved to waitlist instead.'
                    if request.headers.get('Accept') == 'application/json':
                        return jsonify({'success': False, 'message': message})
                    flash(message, 'error')
                    return redirect(url_for('events.event_detail', event_id=event_id))
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

    # Check if event is in the past
    from datetime import datetime
    current_time = datetime.now()
    if event.exact_time < current_time:
        flash("You can't manage attendance on a past event.", 'error')
        return redirect(url_for('events.event_detail', event_id=event_id))

    # Get all RSVPs
    rsvps_attending = list(RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).order_by(RSVP.created_at))

    rsvps_waitlist = list(RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(RSVP.created_at))

    rsvps_not_attending = list(RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).order_by(RSVP.created_at))

    # Calculate counts
    rsvp_count = len(rsvps_attending)
    waitlist_count = len(rsvps_waitlist)
    not_attending_count = len(rsvps_not_attending)

    # Prepare host information for template
    organizer_id = event.organizer_id
    co_host_id = None
    if event.co_host:
        co_host_id = event.co_host.id
    
    # Check if event has passed (current time > event end time, or exact_time if no end_time)
    from datetime import datetime
    current_time = datetime.now()
    event_end_time = event.end_time if event.end_time else event.exact_time
    event_has_passed = current_time > event_end_time

    # Get no-show data for this event
    no_shows = {}
    if event_has_passed:
        # Get all no-show records for this event
        no_show_records = NoShow.select().where(NoShow.event == event)
        no_shows = {no_show.user.id: no_show for no_show in no_show_records}

    # Get total no-show counts for all users (for upcoming events only)
    user_no_show_counts = {}
    if not event_has_passed:
        # Collect all unique user IDs from RSVPs
        all_user_ids = set()
        for rsvp in rsvps_attending + rsvps_waitlist + rsvps_not_attending:
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
        pronoun_counts = {}
        
        for user in attending_users:
            if user.pronouns:
                pronouns = user.pronouns.strip()
                pronoun_counts[pronouns] = pronoun_counts.get(pronouns, 0) + 1
        
        pronoun_stats = {
            'pronouns': pronoun_counts
        }
        
    except Exception as e:
        print(f"Error calculating pronoun statistics: {e}")
        pronoun_stats = {'pronouns': {}}

    return render_template('events/edit_attendance.html',
                           event=event,
                           rsvps_attending=rsvps_attending,
                           rsvps_waitlist=rsvps_waitlist,
                           rsvps_not_attending=rsvps_not_attending,
                           rsvp_count=rsvp_count,
                           waitlist_count=waitlist_count,
                           not_attending_count=not_attending_count,
                           organizer_id=organizer_id,
                           co_host_id=co_host_id,
                           event_has_passed=event_has_passed,
                           no_shows=no_shows,
                           user_no_show_counts=user_no_show_counts,
                           pronoun_stats=pronoun_stats,
                           now=current_time)