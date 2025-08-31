"""
Events routes for cosypolyamory.org

Handles event listing, creation, editing, and RSVP functionality.
"""

import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user

from cosypolyamory.models.user import User
from cosypolyamory.models.event import Event
from cosypolyamory.models.rsvp import RSVP
from cosypolyamory.models.event_note import EventNote
from cosypolyamory.database import database
from cosypolyamory.decorators import organizer_required, approved_user_required
from cosypolyamory.utils import extract_google_maps_info
from cosypolyamory.notification import send_notification_email, send_rsvp_confirmation, notify_event_updated, notify_event_cancelled, notify_host_assigned, notify_host_removed, send_waitlist_promotion_notification, send_rsvp_update_notification, send_rsvp_update_notification

bp = Blueprint('events', __name__, url_prefix='/events')


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
            flash(message, 'info')
            return redirect(url_for('user.application_status'))
        return f(*args, **kwargs)

    return decorated_function


@bp.route('/')
def events_list():
    """List all events with appropriate visibility"""
    now_dt = datetime.now()

    # Fetch upcoming events (future events)
    upcoming_events = Event.select().where((Event.is_active == True) & (Event.exact_time >= now_dt)).order_by(Event.exact_time)

    # Fetch past events (events that have already happened)
    past_events = Event.select().where((Event.is_active == True) & (Event.exact_time < now_dt)).order_by(Event.exact_time.desc())

    can_see_details = current_user.is_authenticated and current_user.can_see_full_event_details()

    # Get user RSVPs for easy access in template
    user_rsvps = {}
    if current_user.is_authenticated and current_user.role in ['approved', 'admin', 'organizer']:
        rsvps = RSVP.select().where(RSVP.user == current_user)
        user_rsvps = {rsvp.event.id: rsvp for rsvp in rsvps}

    # Get RSVP counts for each event (both upcoming and past)
    rsvp_counts = {}
    all_events = list(upcoming_events) + list(past_events)
    for event in all_events:
        count = RSVP.select().where(RSVP.event == event, RSVP.status == 'yes').count()
        rsvp_counts[event.id] = count

    # Strip leading/trailing whitespace from descriptions only
    class EventWithStrippedDesc:

        def __init__(self, event):
            self._event = event
            for attr in dir(event):
                if not attr.startswith('__') and not hasattr(self, attr):
                    setattr(self, attr, getattr(event, attr))
            self.description = (event.description or "").strip()

    upcoming_events_stripped = [EventWithStrippedDesc(e) for e in upcoming_events]
    past_events_stripped = [EventWithStrippedDesc(e) for e in past_events]

    # Provide both upcoming and past events to template
    # Also keep 'events' for backward compatibility with existing template logic
    events_stripped = upcoming_events_stripped + past_events_stripped

    return render_template('events/events_list.html',
                           events=events_stripped,
                           upcoming_events=upcoming_events_stripped,
                           past_events=past_events_stripped,
                           can_see_details=can_see_details,
                           user_rsvps=user_rsvps,
                           rsvp_counts=rsvp_counts,
                           now=datetime.now())


@bp.route('/<int:event_id>')
@approved_user_required
def event_detail(event_id):
    """Show event details"""
    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events.events_list'))

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
    rsvps = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).order_by(RSVP.created_at)
    rsvps_no = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).order_by(RSVP.created_at)
    rsvps_waitlist = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(RSVP.created_at)
    # Extract Google Maps information
    google_maps_info = extract_google_maps_info(event.google_maps_link) if event.google_maps_link else None
    is_user_waitlisted = user_rsvp and user_rsvp.status == 'waitlist'

    # Check if user can manage RSVPs (admin, organizer, or event host)
    can_manage_rsvps = (current_user.is_authenticated and (current_user.role == 'admin' or current_user.can_organize_events()
                                                           or current_user.id == event.organizer_id))

    # Prepare calendar data for Add to Calendar feature
    from datetime import timedelta

    # For approved users, use exact times
    if can_see_details:
        calendar_start = event.exact_time.strftime('%Y%m%dT%H%M%S')
        if event.end_time:
            calendar_end = event.end_time.strftime('%Y%m%dT%H%M%S')
        else:
            # Default to 2 hours if no end time specified
            calendar_end = (event.exact_time + timedelta(hours=2)).strftime('%Y%m%dT%H%M%S')
        calendar_location = event.establishment_name
        if event.google_maps_link:
            calendar_location += f", {event.google_maps_link}"
    else:
        # For non-approved users, use general date
        calendar_start = event.date.strftime('%Y%m%dT%H%M%S')
        calendar_end = (event.date + timedelta(hours=2)).strftime('%Y%m%dT%H%M%S')
        calendar_location = event.barrio

    return render_template('events/event_detail.html',
                           event=event,
                           can_see_details=can_see_details,
                           user_rsvp=user_rsvp,
                           rsvp_count=rsvp_count,
                           rsvp_no_count=rsvp_no_count,
                           rsvps=rsvps,
                           rsvps_no=rsvps_no,
                           rsvps_waitlist=rsvps_waitlist,
                           is_user_waitlisted=is_user_waitlisted,
                           can_manage_rsvps=can_manage_rsvps,
                           google_maps_api_key=os.getenv('GOOGLE_MAPS_API_KEY'),
                           google_maps_info=google_maps_info,
                           now=datetime.now(),
                           calendar_start=calendar_start,
                           calendar_end=calendar_end,
                           calendar_location=calendar_location)


@bp.route('/create')
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
    event_notes = list(EventNote.select().order_by(EventNote.name))
    from datetime import datetime, timedelta
    default_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
    default_hour = '19'
    default_minute = '00'
    return render_template('events/create_event.html',
                           organizers=organizer_list,
                           event_notes=event_notes,
                           default_date=default_date,
                           default_hour=default_hour,
                           default_minute=default_minute)


@bp.route('/create', methods=['POST'])
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

        # Handle time from either new dropdowns or old time input
        time_str = request.form.get('time')
        time_hour = request.form.get('time_hour')
        time_minute = request.form.get('time_minute')

        if time_hour and time_minute:
            time_str = f"{time_hour}:{time_minute}"
        elif not time_str:
            flash('Please select a time for the event.', 'error')
            return redirect(url_for('events.create_event'))

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
            return redirect(url_for('events.create_event'))

        try:
            organizer = User.get_by_id(organizer_id)
            if not organizer.can_organize_events():
                flash('Selected organizer does not have permission to organize events.', 'error')
                return redirect(url_for('events.create_event'))
        except User.DoesNotExist:
            flash('Selected organizer not found.', 'error')
            return redirect(url_for('events.create_event'))

        # Check permission: only admins or the selected organizer can create events for that organizer
        if not (current_user.role == 'admin' or current_user.id == organizer_id):
            flash('You can only create events as yourself unless you are an admin.', 'error')
            return redirect(url_for('events.create_event'))

        # Parse dates and times
        date = dt.strptime(date_str, '%Y-%m-%d')
        exact_time = dt.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')

        # Check if organizer and co-host need RSVPs and if there's space for them
        if max_attendees:
            max_capacity = int(max_attendees)

            # Check if organizer already has an RSVP for this event (shouldn't happen in create, but let's be safe)
            organizer_needs_rsvp = True
            cohost_needs_rsvp = bool(co_host)

            try:
                # This shouldn't exist for a new event, but check anyway
                existing_organizer_rsvp = RSVP.get((RSVP.user == organizer))
                if existing_organizer_rsvp.status == 'yes':
                    organizer_needs_rsvp = False
            except RSVP.DoesNotExist:
                pass

            if co_host:
                try:
                    # This shouldn't exist for a new event, but check anyway
                    existing_cohost_rsvp = RSVP.get((RSVP.user == co_host))
                    if existing_cohost_rsvp.status == 'yes':
                        cohost_needs_rsvp = False
                except RSVP.DoesNotExist:
                    pass

            # Calculate how many RSVPs we need to create
            rsvps_needed = (1 if organizer_needs_rsvp else 0) + (1 if cohost_needs_rsvp else 0)

            if rsvps_needed > max_capacity:
                if co_host:
                    flash(
                        f'Cannot create event with capacity of {max_capacity}. The organizer and co-host need RSVPs but there is not enough space for them in the event.',
                        'error')
                else:
                    flash(
                        f'Cannot create event with capacity of {max_capacity}. The organizer needs an RSVP but there is not enough space in the event.',
                        'error')
                return redirect(url_for('events.create_event'))

        # Validate Google Maps link if provided
        valid_maps_domains = ['maps.google.com', 'www.google.com/maps', 'maps.app.goo.gl', 'goo.gl/maps']
        if google_maps_link:
            is_valid_maps_link = any(domain in google_maps_link.lower() for domain in valid_maps_domains)
            if not is_valid_maps_link:
                flash(
                    'If provided, Google Maps link must be from Google Maps (maps.google.com, www.google.com/maps, or maps.app.goo.gl).',
                    'error')
                return redirect(url_for('events.create_event'))

        # Handle co-host
        co_host = None
        if co_host_id:
            try:
                co_host = User.get_by_id(co_host_id)
                if not co_host.can_organize_events():
                    flash('Co-host must be an organizer.', 'error')
                    return redirect(url_for('events.create_event'))
            except User.DoesNotExist:
                flash('Co-host not found.', 'error')
                return redirect(url_for('events.create_event'))

        # Handle event note
        event_note_id = request.form.get('event_note_id')
        event_note = None
        if event_note_id:
            try:
                event_note = EventNote.get_by_id(event_note_id)
            except EventNote.DoesNotExist:
                flash('Selected event note not found.', 'error')
                return redirect(url_for('events.create_event'))

        # Validate max_attendees against required host RSVPs
        required_hosts = 1  # organizer
        if co_host:
            required_hosts = 2  # organizer + co-host

        if max_attendees and int(max_attendees) < required_hosts:
            flash(
                f'Cannot create event with capacity of {max_attendees}. Minimum capacity must be at least {required_hosts} to accommodate the organizer{" and co-host" if co_host else ""}.',
                'error')
            return redirect(url_for('events.create_event'))

        # Handle end time from hour/minute dropdowns
        end_time_hour = request.form.get('end_time_hour')
        end_time_minute = request.form.get('end_time_minute')
        end_time = None

        if end_time_hour and end_time_minute:
            try:
                end_time_str = f"{end_time_hour}:{end_time_minute}"
                end_time = datetime.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M")
            except Exception:
                flash('Invalid end time format.', 'error')
                return redirect(url_for('events.create_event'))
        else:
            flash('End time is required for all events.', 'error')
            return redirect(url_for('events.create_event'))

        # Create event and automatic RSVPs in a transaction
        with database.atomic():
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
                end_time=end_time,
                organizer=organizer,
                co_host=co_host,
                tips_for_attendees=tips_for_attendees.strip() if tips_for_attendees and tips_for_attendees.strip() else None,
                max_attendees=int(max_attendees) if max_attendees else None,
                event_note=event_note)

            # Automatically create RSVPs for organizer and co-host
            # Create or update organizer RSVP
            organizer_rsvp, created = RSVP.get_or_create(event=event,
                                                         user=organizer,
                                                         defaults={
                                                             'status': 'yes',
                                                             'created_at': datetime.now(),
                                                             'updated_at': datetime.now()
                                                         })
            if not created and organizer_rsvp.status != 'yes':
                organizer_rsvp.status = 'yes'
                organizer_rsvp.updated_at = datetime.now()
                organizer_rsvp.save()

            # Create or update co-host RSVP if there is a co-host
            if co_host:
                cohost_rsvp, created = RSVP.get_or_create(event=event,
                                                          user=co_host,
                                                          defaults={
                                                              'status': 'yes',
                                                              'created_at': datetime.now(),
                                                              'updated_at': datetime.now()
                                                          })
                if not created and cohost_rsvp.status != 'yes':
                    cohost_rsvp.status = 'yes'
                    cohost_rsvp.updated_at = datetime.now()
                    cohost_rsvp.save()

        # Send host assignment notifications for new event
        try:
            # Notify the organizer (host)
            notify_host_assigned(organizer, event, role="host")

            # Notify co-host if assigned
            if co_host and co_host.id != current_user.id:
                notify_host_assigned(co_host, event, role="co-host")

        except Exception as e:
            current_app.logger.error(f"Failed to send host assignment notifications for event {event.id}: {e}")

        flash(f'Event "{title}" has been created successfully!', 'success')
        return redirect(url_for('events.event_detail', event_id=event.id))

    except ValueError as e:
        flash(f'Error creating event: {str(e)}', 'error')
        return redirect(url_for('events.create_event'))
    except Exception as e:
        flash(f'Unexpected error: {str(e)}', 'error')
        return redirect(url_for('events.create_event'))


@bp.route('/<int:event_id>/edit')
@login_required
def edit_event(event_id):
    """Edit event form"""
    try:
        event = Event.get_by_id(event_id)

        # Check permissions - only admin, organizers, or event creator can edit
        if not (current_user.role in ['admin', 'organizer'] or event.organizer_id == current_user.id):
            flash('You do not have permission to edit this event.', 'error')
            return redirect(url_for('events.event_detail', event_id=event_id))

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
        event_notes = list(EventNote.select().order_by(EventNote.name))
        # Provide default_hour and default_minute for time dropdowns
        default_hour = '19'
        default_minute = '00'
        return render_template('events/create_event.html',
                               event=event,
                               is_edit=True,
                               organizers=organizer_list,
                               event_notes=event_notes,
                               default_hour=default_hour,
                               default_minute=default_minute)
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events.events_list'))


@bp.route('/<int:event_id>/edit', methods=['POST'])
@login_required
def edit_event_post(event_id):
    """Update event"""
    from datetime import datetime as dt

    try:
        event = Event.get_by_id(event_id)

        # Check permissions
        if not (current_user.role in ['admin', 'organizer'] or event.organizer_id == current_user.id):
            flash('You do not have permission to edit this event.', 'error')
            return redirect(url_for('events.event_detail', event_id=event_id))

        # Parse the form data
        title = request.form.get('title')
        description = request.form.get('description')
        barrio = request.form.get('barrio')
        time_period = request.form.get('time_period')
        date_str = request.form.get('date')

        # Handle time from either new dropdowns or old time input
        time_str = request.form.get('time')
        time_hour = request.form.get('time_hour')
        time_minute = request.form.get('time_minute')

        if time_hour and time_minute:
            time_str = f"{time_hour}:{time_minute}"
        elif not time_str:
            flash('Please select a time for the event.', 'error')
            return redirect(url_for('events.edit_event', event_id=event_id))

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
            return redirect(url_for('events.edit_event', event_id=event_id))

        try:
            organizer = User.get_by_id(organizer_id)
            if not organizer.can_organize_events():
                flash('Selected organizer does not have permission to organize events.', 'error')
                return redirect(url_for('events.edit_event', event_id=event_id))
        except User.DoesNotExist:
            flash('Selected organizer not found.', 'error')
            return redirect(url_for('events.edit_event', event_id=event_id))

        # Check permission: only admins, organizers, or the original/new organizer can edit
        if not (current_user.role in ['admin', 'organizer'] or current_user.id == event.organizer_id
                or current_user.id == organizer_id):
            flash('You can only edit events you organize unless you are an admin or organizer.', 'error')
            return redirect(url_for('events.edit_event', event_id=event_id))

        # Parse dates and times
        date = dt.strptime(date_str, '%Y-%m-%d')
        exact_time = dt.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')

        # Parse end_time from form dropdowns
        end_time_hour = request.form.get('end_time_hour')
        end_time_minute = request.form.get('end_time_minute')
        end_time = None

        if end_time_hour and end_time_minute:
            try:
                end_time_str = f"{end_time_hour}:{end_time_minute}"
                end_time = dt.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M")
            except Exception:
                flash('Invalid end time format.', 'error')
                return redirect(url_for('events.edit_event', event_id=event_id))
        else:
            flash('End time is required for all events.', 'error')
            return redirect(url_for('events.edit_event', event_id=event_id))

        # Validate Google Maps link if provided
        valid_maps_domains = ['maps.google.com', 'www.google.com/maps', 'maps.app.goo.gl', 'goo.gl/maps']
        if google_maps_link:
            is_valid_maps_link = any(domain in google_maps_link.lower() for domain in valid_maps_domains)
            if not is_valid_maps_link:
                flash(
                    'If provided, Google Maps link must be from Google Maps (maps.google.com, www.google.com/maps, or maps.app.goo.gl).',
                    'error')
                return redirect(url_for('events.edit_event', event_id=event_id))

        # Handle co-host
        co_host = None
        if co_host_id:
            try:
                co_host = User.get_by_id(co_host_id)
                if not co_host.can_organize_events():
                    flash('Co-host must be an organizer.', 'error')
                    return redirect(url_for('events.edit_event', event_id=event_id))
            except User.DoesNotExist:
                flash('Co-host not found.', 'error')
                return redirect(url_for('events.edit_event', event_id=event_id))
        else:
            # Co-host is being removed
            if event.co_host:
                try:
                    cohost_rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == event.co_host))
                    cohost_rsvp.delete_instance()
                    flash("Co-host and their RSVP have been removed.", 'info')
                except RSVP.DoesNotExist:
                    pass

        event_note_id = request.form.get('event_note_id')
        event_note = None
        if event_note_id:
            try:
                event_note = EventNote.get_by_id(event_note_id)
            except EventNote.DoesNotExist:
                flash('Selected event note not found.', 'error')
                return redirect(url_for('events.edit_event', event_id=event_id))

        # Validate capacity reduction
        if max_attendees:
            new_max_attendees = int(max_attendees)
            current_attending_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()

            if current_attending_count > new_max_attendees:
                edit_attendance_url = url_for('events.edit_attendance', event_id=event_id)
                flash(
                    f'Cannot reduce event capacity to {new_max_attendees}. There are currently {current_attending_count} people attending. Please <a href="{edit_attendance_url}">manage attendance</a> to remove some attendees before reducing the capacity.',
                    'error')
                return redirect(url_for('events.edit_event', event_id=event_id))

            # Check if organizer and co-host have RSVPs and if there's space for them
            # Get current RSVPs for organizer and co-host
            organizer_needs_rsvp = False
            cohost_needs_rsvp = False

            try:
                organizer_rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == organizer))
                if organizer_rsvp.status != 'yes':
                    organizer_needs_rsvp = True
            except RSVP.DoesNotExist:
                organizer_needs_rsvp = True

            if co_host:
                try:
                    cohost_rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == co_host))
                    if cohost_rsvp.status != 'yes':
                        cohost_needs_rsvp = True
                except RSVP.DoesNotExist:
                    cohost_needs_rsvp = True

            # Calculate how many additional RSVPs we need
            additional_rsvps_needed = (1 if organizer_needs_rsvp else 0) + (1 if cohost_needs_rsvp else 0)

            if current_attending_count + additional_rsvps_needed > new_max_attendees:
                missing_hosts = []
                if organizer_needs_rsvp:
                    missing_hosts.append("organizer")
                if cohost_needs_rsvp:
                    missing_hosts.append("co-host")

                if len(missing_hosts) == 1:
                    flash(
                        f'Cannot save event changes. The {missing_hosts[0]} needs an RSVP but there is not enough space in the event (capacity: {new_max_attendees}, current attending: {current_attending_count}).',
                        'error')
                else:
                    flash(
                        f'Cannot save event changes. The {" and ".join(missing_hosts)} need RSVPs but there is not enough space in the event (capacity: {new_max_attendees}, current attending: {current_attending_count}).',
                        'error')
                return redirect(url_for('events.edit_event', event_id=event_id))

            # Check for capacity increase that would allow waitlist promotion
            old_max_attendees = event.max_attendees
            if (old_max_attendees and new_max_attendees > old_max_attendees) or (not old_max_attendees and new_max_attendees):
                # Event capacity is being increased - check for waitlisted users
                available_spots = new_max_attendees - current_attending_count
                waitlisted_users = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(
                    RSVP.created_at).limit(available_spots)

                if waitlisted_users.exists():
                    # Check if this is a confirmation request
                    if request.form.get('confirm_promotions') == 'true':
                        # Promote waitlisted users to attending
                        promoted_users = []
                        for rsvp in waitlisted_users:
                            rsvp.status = 'yes'
                            rsvp.updated_at = datetime.now()
                            rsvp.save()
                            promoted_users.append(rsvp.user.name)
                            # Send notification to promoted user
                            send_waitlist_promotion_notification(rsvp.user, event)

                        # Continue with normal event save
                        promotion_message = f" {len(promoted_users)} people were promoted from waitlist: {', '.join(promoted_users)}"
                    else:
                        # Return list of users who would be promoted for confirmation
                        users_to_promote = [{'name': rsvp.user.name, 'id': rsvp.user.id} for rsvp in waitlisted_users]

                        if request.headers.get('Accept') == 'application/json':
                            return jsonify({
                                'needs_confirmation': True,
                                'users_to_promote': users_to_promote,
                                'available_spots': available_spots
                            })
                        else:
                            # For non-AJAX requests, show a different error message directing to use the interface
                            flash(
                                f'Increasing capacity to {new_max_attendees} would promote {len(users_to_promote)} people from waitlist. Please use the web interface to confirm this change.',
                                'info')
                            return redirect(url_for('events.edit_event', event_id=event_id))

        # Update event and RSVPs in a transaction
        with database.atomic():
            # Track changes for notifications
            changes = []
            old_establishment_name = event.establishment_name
            old_exact_time = event.exact_time
            old_end_time = event.end_time
            old_date = event.date
            old_organizer = event.organizer
            old_co_host = event.co_host

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
            event.end_time = end_time
            event.organizer = organizer
            event.co_host = co_host
            event.tips_for_attendees = tips_for_attendees.strip() if tips_for_attendees and tips_for_attendees.strip() else None
            event.max_attendees = int(max_attendees) if max_attendees else None
            event.event_note = event_note
            event.save()

            # Check for significant changes that warrant notifications
            if old_establishment_name != establishment_name:
                changes.append(f"Location changed from '{old_establishment_name}' to '{establishment_name}'")

            if old_exact_time != exact_time:
                old_time_str = old_exact_time.strftime('%I:%M %p')
                new_time_str = exact_time.strftime('%I:%M %p')
                changes.append(f"Start time changed from {old_time_str} to {new_time_str}")

            if old_end_time != end_time:
                old_end_str = old_end_time.strftime('%I:%M %p') if old_end_time else "No end time"
                new_end_str = end_time.strftime('%I:%M %p') if end_time else "No end time"
                changes.append(f"End time changed from {old_end_str} to {new_end_str}")

            if old_date.date() != date.date():
                old_date_str = old_date.strftime('%A, %B %d, %Y')
                new_date_str = date.strftime('%A, %B %d, %Y')
                changes.append(f"Date changed from {old_date_str} to {new_date_str}")

            # Automatically create/update RSVPs for organizer and co-host
            # Create or update organizer RSVP
            organizer_rsvp, created = RSVP.get_or_create(event=event,
                                                         user=organizer,
                                                         defaults={
                                                             'status': 'yes',
                                                             'created_at': datetime.now(),
                                                             'updated_at': datetime.now()
                                                         })
            if not created and organizer_rsvp.status != 'yes':
                organizer_rsvp.status = 'yes'
                organizer_rsvp.updated_at = datetime.now()
                organizer_rsvp.save()

            # Create or update co-host RSVP if there is a co-host
            if co_host:
                cohost_rsvp, created = RSVP.get_or_create(event=event,
                                                          user=co_host,
                                                          defaults={
                                                              'status': 'yes',
                                                              'created_at': datetime.now(),
                                                              'updated_at': datetime.now()
                                                          })
                if not created and cohost_rsvp.status != 'yes':
                    cohost_rsvp.status = 'yes'
                    cohost_rsvp.updated_at = datetime.now()
                    cohost_rsvp.save()

        # Send notifications for significant changes
        if changes:
            # Get all RSVPed users
            rsvped_users = (User.select().join(RSVP).where((RSVP.event == event) & (RSVP.status == 'yes')))

            # Send update notifications to all attendees
            for user in rsvped_users:
                try:
                    notify_event_updated(user, event, changes=changes)
                except Exception as e:
                    current_app.logger.error(f"Failed to send event update notification to {user.email}: {e}")

            if len(changes) > 0:
                change_count = len(changes)
                attendee_count = rsvped_users.count()
                current_app.logger.info(f"Sent event update notifications for {change_count} changes to {attendee_count} attendees")

        # Send host assignment/removal notifications
        try:
            # Check for organizer changes
            if old_organizer.id != organizer.id:
                # Notify new organizer
                notify_host_assigned(organizer, event, role="host")

                # Optionally notify old organizer about removal (if not the person making the change)
                if old_organizer.id != current_user.id:
                    # Send notification about host role removal
                    notify_host_removed(old_organizer, event, "host")

            # Check for co-host changes
            if old_co_host != co_host:
                # If co-host was added
                if co_host and not old_co_host:
                    if co_host.id != current_user.id:
                        notify_host_assigned(co_host, event, role="co-host")
                # If co-host was changed
                elif co_host and old_co_host and co_host.id != old_co_host.id:
                    # Notify new co-host
                    if co_host.id != current_user.id:
                        notify_host_assigned(co_host, event, role="co-host")
                    # Notify old co-host about removal
                    if old_co_host.id != current_user.id:
                        notify_host_removed(old_co_host, event, "co-host")
                # If co-host was removed
                elif not co_host and old_co_host:
                    if old_co_host.id != current_user.id:
                        notify_host_removed(old_co_host, event, "co-host")

        except Exception as e:
            current_app.logger.error(f"Failed to send host change notifications for event {event.id}: {e}")

        success_message = f'Event "{title}" has been updated successfully!'
        if 'promotion_message' in locals():
            success_message += promotion_message

        flash(success_message, 'success')
        return redirect(url_for('events.event_detail', event_id=event.id))

    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events.events_list'))
    except ValueError as e:
        flash(f'Error updating event: {str(e)}', 'error')
        return redirect(url_for('events.edit_event', event_id=event_id))
    except Exception as e:
        flash(f'Unexpected error: {str(e)}', 'error')
        return redirect(url_for('events.edit_event', event_id=event_id))


@bp.route('/<int:event_id>/rsvp', methods=['POST'])
@approved_user_required
def rsvp_event(event_id):
    """RSVP to an event"""
    from flask import jsonify

    print("RSVP handler!")

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
                    print("meh")
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
                print("meh2")
            return redirect(url_for('events.event_detail', event_id=event_id))

        if status not in ['yes', 'no', 'maybe']:
            message = 'Invalid attendance status.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
            print("meh3")
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

            print("mop2")

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

            # Automatic waitlist promotion when someone who was attending is removed
            promoted_user = None
            if prev_status == 'yes' and event.max_attendees:
                yes_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
                if yes_count < event.max_attendees:
                    next_waitlisted = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(
                        RSVP.created_at).first()
                    if next_waitlisted:
                        next_waitlisted.status = 'yes'
                        next_waitlisted.updated_at = datetime.now()
                        next_waitlisted.save()
                        promoted_user = next_waitlisted.user.name
                        # Send waitlist promotion notification
                        send_waitlist_promotion_notification(next_waitlisted.user, event)

            message = f'RSVP removed for {target_user.name}'
            if promoted_user:
                message += f'. {promoted_user} has been moved from waitlist to attending.'

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

            # Automatic waitlist promotion when someone moves from attending to not attending
            promoted_user = None
            if prev_status == 'yes' and new_status != 'yes' and event.max_attendees:
                yes_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
                if yes_count < event.max_attendees:
                    next_waitlisted = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(
                        RSVP.created_at).first()
                    if next_waitlisted:
                        next_waitlisted.status = 'yes'
                        next_waitlisted.updated_at = datetime.now()
                        next_waitlisted.save()
                        promoted_user = next_waitlisted.user.name
                        # Send waitlist promotion notification
                        send_waitlist_promotion_notification(next_waitlisted.user, event)
                        message += f' {promoted_user} was promoted from waitlist.'

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

    return render_template('events/edit_attendance.html',
                           event=event,
                           rsvps_attending=rsvps_attending,
                           rsvps_waitlist=rsvps_waitlist,
                           rsvps_not_attending=rsvps_not_attending,
                           rsvp_count=rsvp_count,
                           waitlist_count=waitlist_count,
                           not_attending_count=not_attending_count,
                           organizer_id=organizer_id,
                           co_host_id=co_host_id)


@bp.route('/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    """Delete an event and all associated data"""
    try:
        with database.atomic():
            event = Event.get_by_id(event_id)

            # Check permissions - only admin, organizers, or event creator can delete
            if not current_user.role in ['admin', 'organizer']:
                flash('You do not have permission to delete this event.', 'error')
                return redirect(url_for('events.event_detail', event_id=event_id))

            # Get all RSVPed users (both attending and waitlisted) before deleting the event
            rsvped_users = list(User.select().join(RSVP).where((RSVP.event == event) & (RSVP.status.in_(['yes', 'waitlist']))))

            # Store event info for notifications
            event_title = event.title
            event_date = event.date
            event_time = event.exact_time
            event_location = event.establishment_name

            # Delete all RSVPs associated with this event
            RSVP.delete().where(RSVP.event == event).execute()

            # Delete the event itself
            event.delete_instance()

        # Send cancellation notifications to all attendees (after transaction completes)
        for user in rsvped_users:
            try:
                # Use send_notification_email directly with the stored event data
                from cosypolyamory.notification import send_notification_email
                send_notification_email(to_email=user.email,
                                        template_name="event_cancelled",
                                        name=user.name,
                                        event_title=event_title,
                                        event_date=event_date.strftime('%A, %B %d, %Y'),
                                        event_time=event_time.strftime('%I:%M %p') if event_time else "TBD",
                                        event_location=event_location,
                                        cancellation_reason="This event has been cancelled by the organizers.",
                                        base_url=current_app.config.get('BASE_URL', 'https://cosypolyamory.org'))
            except Exception as e:
                current_app.logger.error(f"Failed to send event cancellation notification to {user.email}: {e}")

        attendee_count = len(rsvped_users)
        if attendee_count > 0:
            current_app.logger.info(f"Sent event cancellation notifications to {attendee_count} attendees")

        flash(f'Event "{event_title}" has been successfully deleted.', 'success')
        return redirect(url_for('events.events_list'))

    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events.events_list'))
    except Exception as e:
        flash(f'An error occurred while deleting the event: {str(e)}', 'error')
        return redirect(url_for('events.edit_event', event_id=event_id))
