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
from cosypolyamory.models.no_show import NoShow
from cosypolyamory.database import database
from cosypolyamory.decorators import organizer_required, approved_user_required
from cosypolyamory.utils import extract_google_maps_info
from cosypolyamory.notification import send_notification_email, send_rsvp_confirmation, notify_event_updated, notify_event_cancelled, notify_host_assigned, notify_host_removed, send_waitlist_promotion_notification, send_rsvp_update_notification, send_rsvp_update_notification
from cosypolyamory.routes.attendance import process_attendance_changes

bp = Blueprint('events', __name__, url_prefix='/events')


def validate_event_form_data(title, description, barrio, establishment_name, tips_for_attendees, 
                           location_notes=None, google_maps_link=None):
    """
    Validate event form data for character limits and required fields.
    
    Returns (is_valid, error_message)
    """
    # Required field validation
    if not title or not title.strip():
        return False, "Event title is required."
    
    if not description or not description.strip():
        return False, "Event description is required."
    
    if not barrio or not barrio.strip():
        return False, "Barrio/neighborhood is required."
    
    # Character limit validation
    if len(title.strip()) > 255:
        return False, f"Event title must be 255 characters or less. Current length: {len(title.strip())}"
    
    if len(description.strip()) > 5000:
        return False, f"Event description must be 5000 characters or less. Current length: {len(description.strip())}"
    
    if len(barrio.strip()) > 64:
        return False, f"Barrio/neighborhood must be 64 characters or less. Current length: {len(barrio.strip())}"
    
    if establishment_name and len(establishment_name.strip()) > 64:
        return False, f"Establishment name must be 64 characters or less. Current length: {len(establishment_name.strip())}"
    
    if tips_for_attendees and len(tips_for_attendees.strip()) > 5000:
        return False, f"Tips for attendees must be 5000 characters or less. Current length: {len(tips_for_attendees.strip())}"
    
    if location_notes and len(location_notes.strip()) > 1000:
        return False, f"Location notes must be 1000 characters or less. Current length: {len(location_notes.strip())}"
    
    if google_maps_link and len(google_maps_link.strip()) > 2000:
        return False, f"Google Maps link must be 2000 characters or less. Current length: {len(google_maps_link.strip())}"
    
    return True, None


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
            return redirect(url_for('auth.profile'))
        return f(*args, **kwargs)

    return decorated_function


@bp.route('/')
def events_list():
    """List all events with appropriate visibility"""
    from flask import request
    
    now_dt = datetime.now()
    
    # Get filter from query parameter, default to 'upcoming'
    current_filter = request.args.get('filter', 'upcoming')
    
    # Determine which events to show based on user role
    if current_user.is_authenticated and current_user.role in ['admin', 'organizer']:
        # Admins and organizers can see all events (including drafts)
        base_query = Event.select().where(Event.is_active == True)
    else:
        # Regular users can only see published events
        base_query = Event.select().where((Event.is_active == True) & (Event.published == True))
    
    if current_filter == 'past':
        # Show only past events
        events = base_query.where(Event.exact_time < now_dt).order_by(Event.exact_time.desc())
        page_title = "Past Events"
    else:
        # Show only upcoming events (default)
        events = base_query.where(Event.exact_time >= now_dt).order_by(Event.exact_time)
        page_title = "Upcoming Events"
        current_filter = 'upcoming'  # Ensure it's set to upcoming for template

    can_see_details = current_user.is_authenticated and current_user.can_see_full_event_details()

    # Get user RSVPs for easy access in template
    user_rsvps = {}
    if current_user.is_authenticated and current_user.role in ['approved', 'admin', 'organizer']:
        rsvps = RSVP.select().where(RSVP.user == current_user)
        user_rsvps = {rsvp.event.id: rsvp for rsvp in rsvps}

    # Get RSVP counts for the filtered events
    rsvp_counts = {}
    rsvps_waitlist = {}
    all_events = list(events)
    for event in all_events:
        count = RSVP.select().where(RSVP.event == event, RSVP.status == 'yes').count()
        rsvp_counts[event.id] = count
        
        # Get waitlist count for this event
        waitlist_count = RSVP.select().where(RSVP.event == event, RSVP.status == 'waitlist').count()
        if waitlist_count > 0:
            rsvps_waitlist[event.id] = waitlist_count

    # Strip leading/trailing whitespace from descriptions only
    class EventWithStrippedDesc:

        def __init__(self, event):
            self._event = event
            for attr in dir(event):
                if not attr.startswith('__') and not hasattr(self, attr):
                    setattr(self, attr, getattr(event, attr))
            self.description = (event.description or "").strip()

    events_stripped = [EventWithStrippedDesc(e) for e in events]

    return render_template('events/events_list.html',
                           events=events_stripped,
                           can_see_details=can_see_details,
                           user_rsvps=user_rsvps,
                           rsvp_counts=rsvp_counts,
                           rsvps_waitlist=rsvps_waitlist,
                           current_filter=current_filter,
                           page_title=page_title,
                           now=now_dt)


@bp.route('/<int:event_id>')
@approved_user_required
def event_detail(event_id):
    """Show event details"""
    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events.events_list'))

    # Check if event is published or if user has permission to view drafts
    if not event.published:
        if not (current_user.is_authenticated and 
                (current_user.role in ['admin', 'organizer'] or 
                 event.organizer_id == current_user.id or 
                 (event.co_host and event.co_host_id == current_user.id))):
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
                           rsvps_maybe=rsvps_maybe,
                           rsvps_waitlist=rsvps_waitlist,
                           consolidated_attendance=consolidated_attendance,
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
    
    # Check if we're cloning an event (query parameters present)
    clone_data = {}
    if request.args:
        # Collect all query parameters for pre-populating the form
        clone_data = {
            'title': request.args.get('title', ''),
            'description': request.args.get('description', ''),
            'barrio': request.args.get('barrio', ''),
            'time_period': request.args.get('time_period', ''),
            'date': request.args.get('date', default_date),
            'time_hour': request.args.get('time_hour', default_hour),
            'time_minute': request.args.get('time_minute', default_minute),
            'establishment_name': request.args.get('establishment_name', ''),
            'google_maps_link': request.args.get('google_maps_link', ''),
            'location_notes': request.args.get('location_notes', ''),
            'organizer_id': request.args.get('organizer_id', ''),
            'co_host_id': request.args.get('co_host_id', ''),
            'tips_for_attendees': request.args.get('tips_for_attendees', ''),
            'max_attendees': request.args.get('max_attendees', ''),
            'event_note_id': request.args.get('event_note_id', ''),
            'is_multiday': request.args.get('is_multiday', '') == 'on',
            'start_date': request.args.get('start_date', ''),
            'end_date': request.args.get('end_date', ''),
            'end_time_hour': request.args.get('end_time_hour', ''),
            'end_time_minute': request.args.get('end_time_minute', ''),
        }
    
    return render_template('events/create_event.html',
                           organizers=organizer_list,
                           event_notes=event_notes,
                           default_date=default_date,
                           default_hour=default_hour,
                           default_minute=default_minute,
                           clone_data=clone_data,
                           now=datetime.now())


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

        # Validate form data lengths and required fields
        is_valid, error_message = validate_event_form_data(
            title, description, barrio, establishment_name, tips_for_attendees,
            location_notes, google_maps_link
        )
        if not is_valid:
            current_app.logger.warning(f"Event creation validation failed for user {current_user.id}: {error_message}")
            flash(error_message, 'error')
            return redirect(url_for('events.create_event'))

        # Validate organizer
        if not organizer_id:
            current_app.logger.warning(f"Event creation failed: No organizer selected by user {current_user.id}")
            flash('Please select a primary organizer.', 'error')
            return redirect(url_for('events.create_event'))

        try:
            organizer = User.get_by_id(organizer_id)
            if not organizer.can_organize_events():
                current_app.logger.warning(f"Event creation failed: User {organizer_id} cannot organize events (user {current_user.id} attempted)")
                flash('Selected organizer does not have permission to organize events.', 'error')
                return redirect(url_for('events.create_event'))
        except User.DoesNotExist:
            current_app.logger.warning(f"Event creation failed: Organizer {organizer_id} not found (user {current_user.id} attempted)")
            flash('Selected organizer not found.', 'error')
            return redirect(url_for('events.create_event'))

        # Handle co-host early, before capacity validation
        co_host = None
        if co_host_id:
            try:
                co_host = User.get_by_id(co_host_id)
                if not co_host.can_organize_events():
                    current_app.logger.warning(f"Event creation failed: Co-host {co_host_id} cannot organize events (user {current_user.id} attempted)")
                    flash('Co-host must be an organizer.', 'error')
                    return redirect(url_for('events.create_event'))
            except User.DoesNotExist:
                current_app.logger.warning(f"Event creation failed: Co-host {co_host_id} not found (user {current_user.id} attempted)")
                flash('Co-host not found.', 'error')
                return redirect(url_for('events.create_event'))

        # Parse dates and times - will be set properly in multiday section below
        date = None
        exact_time = None
        
        # Initial parsing for single day events
        if not request.form.get('is_multiday'):
            try:
                date = dt.strptime(date_str, '%Y-%m-%d')
                exact_time = dt.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
            except ValueError as e:
                flash(f'Invalid date or time format: {str(e)}', 'error')
                return redirect(url_for('events.create_event'))

        # Validate max_attendees is a valid number
        if max_attendees:
            try:
                max_capacity = int(max_attendees)
                if max_capacity < 1:
                    flash('Event capacity must be at least 1.', 'error')
                    return redirect(url_for('events.create_event'))
            except (ValueError, TypeError):
                flash('Event capacity must be a valid number.', 'error')
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

        # Handle event note
        event_note_id = request.form.get('event_note_id')
        event_note = None
        if event_note_id:
            try:
                event_note = EventNote.get_by_id(event_note_id)
            except EventNote.DoesNotExist:
                flash('Selected event note not found.', 'error')
                return redirect(url_for('events.create_event'))
        
        # Check if event should be published immediately
        publish_immediately = request.form.get('publish_immediately') == 'on'

        # Handle end time from hour/minute dropdowns
        end_time_hour = request.form.get('end_time_hour')
        end_time_minute = request.form.get('end_time_minute')
        end_time = None
        
        # Check if this is a multi-day event
        is_multiday = request.form.get('is_multiday') == 'on'
        
        if is_multiday:
            # Use start_date and end_date for multi-day events
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            
            if not start_date_str or not end_date_str:
                flash('Start date and end date are required for multi-day events.', 'error')
                return redirect(url_for('events.create_event'))
            
            try:
                # Parse start datetime
                date = dt.strptime(start_date_str, '%Y-%m-%d')
                exact_time = dt.strptime(f"{start_date_str} {time_str}", '%Y-%m-%d %H:%M')
                
                # Parse end datetime
                if end_time_hour and end_time_minute:
                    end_time_str = f"{end_time_hour}:{end_time_minute}"
                    end_time = dt.strptime(f"{end_date_str} {end_time_str}", "%Y-%m-%d %H:%M")
                else:
                    flash('End time is required for all events.', 'error')
                    return redirect(url_for('events.create_event'))
                
                # Validate that end is after start
                if end_time <= exact_time:
                    flash('Event end date/time must be after start date/time.', 'error')
                    return redirect(url_for('events.create_event'))
                    
            except ValueError as e:
                flash(f'Invalid date or time format: {str(e)}', 'error')
                return redirect(url_for('events.create_event'))
        else:
            # Single day event - use the date field for both start and end
            if end_time_hour and end_time_minute:
                try:
                    end_time_str = f"{end_time_hour}:{end_time_minute}"
                    end_time = datetime.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M")
                    
                    # Validate that end is after start
                    if end_time <= exact_time:
                        flash('Event end time must be after start time.', 'error')
                        return redirect(url_for('events.create_event'))
                except Exception:
                    flash('Invalid end time format.', 'error')
                    return redirect(url_for('events.create_event'))
            else:
                flash('End time is required for all events.', 'error')
                return redirect(url_for('events.create_event'))

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
            event_note=event_note,
            published=publish_immediately)  # Create as draft or published based on checkbox

        # Use process_attendance_changes to create host RSVPs and handle capacity
        # This ensures hosts are added properly and waitlist is promoted if needed
        success, response_data, status_code = process_attendance_changes(
            event.id,
            {},  # Empty data - function will automatically add hosts
            requesting_user_id=None  # Admin privileges to bypass permission checks
        )
        
        if not success:
            # If attendance processing fails, delete the event and show error
            event.delete_instance()
            flash(f'Failed to create event: {response_data.get("error", "Unknown error")}', 'error')
            return redirect(url_for('events.create_event'))

        # Note: Host assignment notifications are sent automatically by process_attendance_changes()

        if publish_immediately:
            flash(f'Event "{title}" has been created and published! Users can now see it and RSVP.', 'success')
            
            # Send Telegram announcement for newly published events
            try:
                from cosypolyamory.telegram_integration import notify_event_created
                notify_event_created(event)
            except Exception as e:
                current_app.logger.error(f"Failed to send Telegram announcement for new event {event.id}: {e}")
            
            # Send email notification to all eligible members
            try:
                from cosypolyamory.notification import notify_event_published
                notify_event_published(event)
            except Exception as e:
                current_app.logger.error(f"Failed to send email notifications for new event {event.id}: {e}")
        else:
            flash(f'Event "{title}" has been created as a draft! Use the "Publish" option to make it visible to users.', 'success')

        return redirect(url_for('events.event_detail', event_id=event.id))

    except ValueError as e:
        current_app.logger.warning(f"Value error creating event: {str(e)}")
        flash(f'Invalid input data: {str(e)}', 'error')
        return redirect(url_for('events.create_event'))
    except (User.DoesNotExist, Event.DoesNotExist, EventNote.DoesNotExist) as e:
        current_app.logger.warning(f"Database object not found when creating event: {str(e)}")
        flash('One of the selected items (organizer, co-host, or event note) could not be found. Please try again.', 'error')
        return redirect(url_for('events.create_event'))
    except Exception as e:
        current_app.logger.error(f"Unexpected error creating event: {str(e)}", exc_info=True)
        flash('An unexpected error occurred while creating the event. Please try again or contact support if the problem persists.', 'error')
        return redirect(url_for('events.create_event'))


@bp.route('/<int:event_id>/edit')
@login_required
def edit_event(event_id):
    """Edit event form"""
    try:
        event = Event.get_by_id(event_id)

        # Check permissions - only admin, organizers, event creator, or co-host can edit
        is_cohost = event.co_host and event.co_host.id == current_user.id
        if not (current_user.role in ['admin', 'organizer'] or event.organizer_id == current_user.id or is_cohost):
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
                               default_minute=default_minute,
                               now=datetime.now())
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

        # Check permissions - allow admin, organizer, event creator, or co-host
        is_cohost = event.co_host and event.co_host.id == current_user.id
        if not (current_user.role in ['admin', 'organizer'] or event.organizer_id == current_user.id or is_cohost):
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
        publish_immediately = request.form.get('publish_immediately') == 'on'

        # Validate form data lengths and required fields
        is_valid, error_message = validate_event_form_data(
            title, description, barrio, establishment_name, tips_for_attendees,
            location_notes, google_maps_link
        )
        if not is_valid:
            current_app.logger.warning(f"Event edit validation failed for user {current_user.id}, event {event_id}: {error_message}")
            flash(error_message, 'error')
            return redirect(url_for('events.edit_event', event_id=event_id))

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

        # Check permission: only admins, organizers, event creator, new organizer, or co-host can edit
        is_cohost = event.co_host and event.co_host.id == current_user.id
        if not (current_user.role in ['admin', 'organizer'] or current_user.id == event.organizer_id
                or current_user.id == organizer_id or is_cohost):
            flash('You can only edit events you organize or co-host unless you are an admin or organizer.', 'error')
            return redirect(url_for('events.edit_event', event_id=event_id))

        # Parse dates and times
        # Check if this is a multi-day event
        is_multiday = request.form.get('is_multiday') == 'on'
        
        if is_multiday:
            # Use start_date and end_date for multi-day events
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            
            if not start_date_str or not end_date_str:
                flash('Start date and end date are required for multi-day events.', 'error')
                return redirect(url_for('events.edit_event', event_id=event_id))
            
            try:
                # Parse start datetime
                date = dt.strptime(start_date_str, '%Y-%m-%d')
                exact_time = dt.strptime(f"{start_date_str} {time_str}", '%Y-%m-%d %H:%M')
                
                # Parse end datetime
                end_time_hour = request.form.get('end_time_hour')
                end_time_minute = request.form.get('end_time_minute')
                
                if end_time_hour and end_time_minute:
                    end_time_str = f"{end_time_hour}:{end_time_minute}"
                    end_time = dt.strptime(f"{end_date_str} {end_time_str}", "%Y-%m-%d %H:%M")
                else:
                    flash('End time is required for all events.', 'error')
                    return redirect(url_for('events.edit_event', event_id=event_id))
                
                # Validate that end is after start
                if end_time <= exact_time:
                    flash('Event end date/time must be after start date/time.', 'error')
                    return redirect(url_for('events.edit_event', event_id=event_id))
                    
            except ValueError as e:
                flash(f'Invalid date or time format: {str(e)}', 'error')
                return redirect(url_for('events.edit_event', event_id=event_id))
        else:
            # Single day event
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
                    
                    # Validate that end is after start
                    if end_time <= exact_time:
                        flash('Event end time must be after start time.', 'error')
                        return redirect(url_for('events.edit_event', event_id=event_id))
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
        
        # Track host/co-host changes for RSVP management
        # We need to remove RSVPs from old hosts before adding new ones
        users_to_remove = []
        
        # Check if organizer changed
        if event.organizer_id != organizer_id:
            users_to_remove.append((event.organizer_id, False))  # Old organizer, don't notify
        
        # Check if co-host changed or was removed
        if event.co_host_id:
            # Old co-host exists
            if not co_host or co_host.id != event.co_host_id:
                # Co-host was removed or changed to someone else
                users_to_remove.append((event.co_host_id, False))  # Old co-host, don't notify

        event_note_id = request.form.get('event_note_id')
        event_note = None
        if event_note_id:
            try:
                event_note = EventNote.get_by_id(event_note_id)
            except EventNote.DoesNotExist:
                flash('Selected event note not found.', 'error')
                return redirect(url_for('events.edit_event', event_id=event_id))

        # Track changes for notifications
        changes = []
        old_establishment_name = event.establishment_name
        old_exact_time = event.exact_time
        old_end_time = event.end_time
        old_date = event.date
        old_organizer = event.organizer
        old_co_host = event.co_host
        old_published = event.published

        # IMPORTANT: Check capacity BEFORE making changes
        # Calculate how many host slots we need
        current_yes_count = RSVP.select().where(
            (RSVP.event == event) & (RSVP.status == 'yes')
        ).count()
        
        # Count how many host RSVPs we currently have
        hosts_with_rsvp = 0
        if event.organizer_id:
            try:
                org_rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == event.organizer))
                if org_rsvp.status == 'yes':
                    hosts_with_rsvp += 1
            except RSVP.DoesNotExist:
                pass
        
        if event.co_host_id:
            try:
                cohost_rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == event.co_host))
                if cohost_rsvp.status == 'yes':
                    hosts_with_rsvp += 1
            except RSVP.DoesNotExist:
                pass
        
        # Count how many host RSVPs we'll need after the change
        new_hosts_needed = 0
        if organizer_id != event.organizer_id:
            # Organizer is changing - need new organizer
            new_hosts_needed += 1
        else:
            # Same organizer - count if they already have RSVP
            try:
                RSVP.get((RSVP.event == event) & (RSVP.user == organizer))
            except RSVP.DoesNotExist:
                new_hosts_needed += 1
        
        if co_host:
            if not event.co_host_id or co_host.id != event.co_host_id:
                # Adding or changing co-host - need new co-host RSVP
                new_hosts_needed += 1
            else:
                # Same co-host - count if they already have RSVP
                try:
                    RSVP.get((RSVP.event == event) & (RSVP.user == co_host))
                except RSVP.DoesNotExist:
                    new_hosts_needed += 1
        
        # Calculate final capacity needs
        # Remove old host RSVPs from count, then check if we can add new ones
        non_host_attendees = current_yes_count - hosts_with_rsvp
        final_needed_spots = non_host_attendees + (1 if organizer else 0) + (1 if co_host else 0)
        
        # Check if new capacity would be exceeded
        new_max_attendees = int(max_attendees) if max_attendees else None
        if new_max_attendees and final_needed_spots > new_max_attendees:
            from markupsafe import Markup
            manage_url = url_for('attendance.edit_attendance', event_id=event.id)
            
            # Check if this is a capacity reduction issue or a host change issue
            if new_max_attendees < event.max_attendees:
                # Capacity is being reduced below current attendance
                flash(Markup(f'Cannot reduce capacity: event currently has {current_yes_count} attendees and cannot be reduced to {new_max_attendees}. Please <a href="{manage_url}" class="alert-link">remove attendees</a> first, then reduce capacity.'), 'error')
            else:
                # Hosts are being changed/added and there's no room
                flash(Markup(f'Cannot update hosts: event is at capacity ({current_yes_count}/{new_max_attendees}). Hosts require attendance spots and there are no available spots. Please increase capacity or <a href="{manage_url}" class="alert-link">remove an attendee</a> first.'), 'error')
            return redirect(url_for('events.edit_event', event_id=event_id))
        
        # IMPORTANT: Remove old host RSVPs BEFORE updating event with new hosts
        # This prevents capacity issues when hosts change
        if users_to_remove:
            attendance_data = {'remove_attendance': users_to_remove}
            
            success, response_data, status_code = process_attendance_changes(
                event.id,
                attendance_data,
                requesting_user_id=None,  # Admin privileges
                no_auto_promote=True  # Don't add current hosts yet - we're about to change them
            )
            
            if not success:
                flash(f'Failed to remove old host RSVPs: {response_data.get("error", "Unknown error")}', 'error')
                return redirect(url_for('events.edit_event', event_id=event_id))

        # Update event (including new hosts)
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
        event.published = publish_immediately
        event.save()

        # Send notifications for host/co-host changes BEFORE updating RSVPs
        # Check if organizer changed
        if old_organizer.id != organizer.id:
            try:
                # Notify old organizer about removal
                notify_host_removed(old_organizer, event, role="host")
            except Exception as e:
                current_app.logger.error(f"Failed to send host removal notification: {e}")
            
            try:
                # Notify new organizer about assignment
                notify_host_assigned(organizer, event, role="host")
            except Exception as e:
                current_app.logger.error(f"Failed to send host assignment notification: {e}")
        
        # Check if co-host changed
        if old_co_host != co_host:
            # If old co-host existed and is different from new co-host
            if old_co_host:
                if not co_host or old_co_host.id != co_host.id:
                    try:
                        notify_host_removed(old_co_host, event, role="co-host")
                    except Exception as e:
                        current_app.logger.error(f"Failed to send co-host removal notification: {e}")
            
            # If new co-host exists and is different from old co-host
            if co_host:
                if not old_co_host or co_host.id != old_co_host.id:
                    try:
                        notify_host_assigned(co_host, event, role="co-host")
                    except Exception as e:
                        current_app.logger.error(f"Failed to send co-host assignment notification: {e}")

        # Always ensure hosts have RSVPs after saving (handles both host changes and additions)
        success, response_data, status_code = process_attendance_changes(
            event.id,
            {},  # Empty data - just let it add host RSVPs
            requesting_user_id=None,  # Admin privileges
            no_auto_promote=False  # Add/update host RSVPs
        )
        
        if not success:
            # This shouldn't happen because we checked capacity above
            # But if it does, we need to revert the event changes
            event.organizer = old_organizer
            event.co_host = old_co_host
            event.save()
            error_msg = response_data.get('error', 'Unknown error')
            flash(f'Failed to update host attendance: {error_msg}. Event reverted to previous hosts.', 'error')
            return redirect(url_for('events.edit_event', event_id=event_id))

        # Check for significant changes that warrant notifications
        if old_establishment_name != establishment_name:
            changes.append(f"Location updated to '{establishment_name}'")

        if old_exact_time != exact_time:
            new_time_str = exact_time.strftime('%H:%M')
            changes.append(f"Start time updated to {new_time_str}")

        if old_end_time != end_time:
            new_end_str = end_time.strftime('%H:%M') if end_time else "No end time"
            changes.append(f"End time updated to {new_end_str}")

        if old_date.date() != date.date():
            new_date_str = date.strftime('%A, %B %d, %Y')
            changes.append(f"Date updated to {new_date_str}")
        
        # Notify about host changes
        if old_organizer.id != organizer.id:
            flash(f"Primary organizer changed from {old_organizer.name} to {organizer.name}.", 'info')
        if old_co_host and not co_host:
            flash(f"Co-host {old_co_host.name} has been removed.", 'info')
        elif old_co_host and co_host and old_co_host.id != co_host.id:
            flash(f"Co-host changed from {old_co_host.name} to {co_host.name}.", 'info')
        elif not old_co_host and co_host:
            flash(f"{co_host.name} has been added as co-host.", 'info')

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

        # Note: Host assignment/removal notifications are sent automatically by process_attendance_changes()
        # when hosts are added/changed/removed

        # Handle publication status changes and Telegram notifications
        if old_published != publish_immediately:
            if publish_immediately:
                # Event was just published
                try:
                    from cosypolyamory.telegram_integration import notify_event_created
                    notify_event_created(event)
                except Exception as e:
                    current_app.logger.error(f"Failed to send Telegram announcement for newly published event {event.id}: {e}")
                
                # Send email notification to all eligible members
                try:
                    from cosypolyamory.notification import notify_event_published
                    notify_event_published(event)
                except Exception as e:
                    current_app.logger.error(f"Failed to send email notifications for newly published event {event.id}: {e}")
            else:
                # Event was unpublished - send unpublish notification
                try:
                    from cosypolyamory.telegram_integration import notify_event_unpublished
                    notify_event_unpublished(event)
                except Exception as e:
                    current_app.logger.error(f"Failed to send Telegram unpublish notification for event {event.id}: {e}")
        elif publish_immediately and changes:
            # Event is published and has updates - send update notification
            try:
                from cosypolyamory.telegram_integration import notify_event_updated
                # Convert changes list to formatted string
                change_details = "\n".join([f"• {change}" for change in changes])
                notify_event_updated(event, change_details)
            except Exception as e:
                current_app.logger.error(f"Failed to send Telegram update announcement for event {event.id}: {e}")

        if 'promotion_message' in locals():
            flash(promotion_message, 'success')

        return redirect(url_for('events.event_detail', event_id=event.id))

    except Event.DoesNotExist:
        current_app.logger.warning(f"Attempt to edit non-existent event {event_id}")
        flash('Event not found.', 'error')
        return redirect(url_for('events.events_list'))
    except ValueError as e:
        current_app.logger.warning(f"Value error updating event {event_id}: {str(e)}")
        flash(f'Invalid input data: {str(e)}', 'error')
        return redirect(url_for('events.edit_event', event_id=event_id))
    except (User.DoesNotExist, EventNote.DoesNotExist) as e:
        current_app.logger.warning(f"Database object not found when updating event {event_id}: {str(e)}")
        flash('One of the selected items (organizer, co-host, or event note) could not be found. Please try again.', 'error')
        return redirect(url_for('events.edit_event', event_id=event_id))
    except Exception as e:
        current_app.logger.error(f"Unexpected error updating event {event_id}: {str(e)}", exc_info=True)
        flash('An unexpected error occurred while updating the event. Please try again or contact support if the problem persists.', 'error')
        return redirect(url_for('events.edit_event', event_id=event_id))


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
            event_was_published = event.published

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
                                        event_time=event_time.strftime('%H:%M') if event_time else "TBD",
                                        event_location=event_location,
                                        cancellation_reason="This event has been cancelled by the organizers.",
                                        base_url=current_app.config.get('BASE_URL', 'https://cosypolyamory.org'))
            except Exception as e:
                current_app.logger.error(f"Failed to send event cancellation notification to {user.email}: {e}")

        attendee_count = len(rsvped_users)
        if attendee_count > 0:
            current_app.logger.info(f"Sent event cancellation notifications to {attendee_count} attendees")

        # Send Telegram announcement for event cancellation (only for published events)
        if event_was_published:
            try:
                from cosypolyamory.telegram_integration import notify_event_cancelled
                # Create a temporary event object for the notification
                class TempEvent:
                    def __init__(self, title, date, exact_time, establishment_name):
                        self.title = title
                        self.date = date
                        self.exact_time = exact_time
                        self.establishment_name = establishment_name
                
                temp_event = TempEvent(event_title, event_date, event_time, event_location)
                notify_event_cancelled(temp_event)
            except Exception as e:
                current_app.logger.error(f"Failed to send Telegram cancellation announcement for event '{event_title}': {e}")

        flash(f'Event "{event_title}" has been successfully deleted.', 'success')
        return redirect(url_for('events.events_list'))

    except Event.DoesNotExist:
        current_app.logger.warning(f"Attempt to delete non-existent event {event_id} by user {current_user.id}")


@bp.route('/<int:event_id>/rsvp', methods=['POST'])
@login_required
@approved_user_required
def rsvp(event_id):
    """Handle RSVP from event detail page via AJAX.
    
    This endpoint wraps the manage_attendance API to provide a simpler
    interface for users managing their own attendance.
    
    Expects form data with 'status' field: yes/no/maybe/waitlist
    Returns JSON with success status and updated counts.
    """
    # Get the desired status from form data
    status = request.form.get('status')
    if not status or status not in ['yes', 'no', 'maybe', 'waitlist']:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400
    
    # Build attendance data for manage_attendance API
    attendance_data = {}
    if status == 'yes':
        attendance_data['attendance_yes'] = [[current_user.id, True]]
    elif status == 'no':
        attendance_data['attendance_no'] = [[current_user.id, True]]
    elif status == 'maybe':
        attendance_data['attendance_maybe'] = [[current_user.id, True]]
    elif status == 'waitlist':
        attendance_data['attendance_waitlist'] = [[current_user.id, True]]
    
    # Call the core attendance processing function
    success, response_data, status_code = process_attendance_changes(
        event_id,
        attendance_data,
        requesting_user_id=current_user.id,
        no_auto_promote=False  # Allow normal auto-promotion for regular users
    )
    
    if not success:
        return jsonify({'success': False, 'message': response_data.get('error', 'Failed to update RSVP')}), status_code
    
    # Return simplified response for frontend
    return jsonify({
        'success': True,
        'message': response_data.get('message', 'Attendance updated'),
        'status': response_data.get('user_status'),
        'rsvp_count': response_data.get('rsvp_count', 0),
        'waitlist_count': response_data.get('waitlist_count', 0)
    }), 200


@bp.route('/<int:event_id>/publish', methods=['POST'])
@organizer_required
def publish_event(event_id):
    """Toggle publish status of an event"""
    try:
        event = Event.get_by_id(event_id)
        
        # Check if user can edit this event - allow admin, organizer role, event creator, or co-host
        is_cohost = event.co_host and event.co_host.id == current_user.id
        if not (current_user.role in ['admin', 'organizer'] or 
                event.organizer_id == current_user.id or 
                is_cohost):
            flash('You do not have permission to publish this event.', 'error')
            return redirect(url_for('events.event_detail', event_id=event_id))
        
        # Get the action from form data
        action = request.form.get('action', 'publish')
        
        if action == 'publish':
            event.published = True
            event.save()
            flash(f'Event "{event.title}" has been published and is now visible to users!', 'success')
            
            # Check if notifications should be sent (default to True if checkbox not present)
            send_notifications = request.form.get('do_not_notify') != 'on'
            
            if send_notifications:
                # Send Telegram notification for newly published events
                try:
                    from cosypolyamory.telegram_integration import notify_event_created
                    notify_event_created(event)
                except Exception as e:
                    current_app.logger.error(f"Failed to send Telegram announcement for published event {event_id}: {e}")
                
                # Send email notification to all eligible members
                try:
                    from cosypolyamory.notification import notify_event_published
                    notify_event_published(event)
                except Exception as e:
                    current_app.logger.error(f"Failed to send email notifications for published event {event_id}: {e}")
            else:
                current_app.logger.info(f"Skipped notifications for published event {event_id} due to do_not_notify flag")
                
        elif action == 'unpublish':
            event.published = False
            event.save()
            flash(f'Event "{event.title}" has been unpublished and is no longer visible to users.', 'info')
            
            # Send Telegram notification for unpublished event
            try:
                from cosypolyamory.telegram_integration import notify_event_unpublished
                notify_event_unpublished(event)
            except Exception as e:
                current_app.logger.error(f"Failed to send Telegram unpublish notification for event {event_id}: {e}")
        
        return redirect(url_for('events.event_detail', event_id=event_id))
        
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events.events_list'))
    except Exception as e:
        current_app.logger.error(f"Error publishing/unpublishing event {event_id}: {e}")
        flash('An error occurred while updating the event.', 'error')
        return redirect(url_for('events.event_detail', event_id=event_id))
        flash('Event not found.', 'error')
        return redirect(url_for('events.events_list'))
    except Exception as e:
        current_app.logger.error(f"Unexpected error deleting event {event_id}: {str(e)}", exc_info=True)
        flash('An unexpected error occurred while deleting the event. Please try again or contact support if the problem persists.', 'error')
        return redirect(url_for('events.edit_event', event_id=event_id))

