"""
Events routes for cosypolyamory.org

Handles event listing, creation, editing, and RSVP functionality.
"""

import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from cosypolyamory.models.user import User
from cosypolyamory.models.event import Event
from cosypolyamory.models.rsvp import RSVP
from cosypolyamory.models.event_note import EventNote
from cosypolyamory.decorators import organizer_required, approved_user_required
from cosypolyamory.utils import extract_google_maps_info

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
    upcoming_events = Event.select().where(
        (Event.is_active == True) & (Event.exact_time >= now_dt)
    ).order_by(Event.exact_time)
    
    # Fetch past events (events that have already happened)
    past_events = Event.select().where(
        (Event.is_active == True) & (Event.exact_time < now_dt)
    ).order_by(Event.exact_time.desc())
    
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
    can_manage_rsvps = (current_user.is_authenticated and 
                       (current_user.role == 'admin' or 
                        current_user.can_organize_events() or 
                        current_user.id == event.organizer_id))
    
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
    return render_template(
        'events/create_event.html',
        organizers=organizer_list,
        event_notes=event_notes,
        default_date=default_date,
        default_hour=default_hour,
        default_minute=default_minute
    )


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
        
        # Validate Google Maps link if provided
        valid_maps_domains = ['maps.google.com', 'www.google.com/maps', 'maps.app.goo.gl', 'goo.gl/maps']
        if google_maps_link:
            is_valid_maps_link = any(domain in google_maps_link.lower() for domain in valid_maps_domains)
            if not is_valid_maps_link:
                flash('If provided, Google Maps link must be from Google Maps (maps.google.com, www.google.com/maps, or maps.app.goo.gl).', 'error')
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
        return render_template('events/create_event.html', event=event, is_edit=True, organizers=organizer_list, event_notes=event_notes)
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
        if not (current_user.role in ['admin', 'organizer'] or current_user.id == event.organizer_id or current_user.id == organizer_id):
            flash('You can only edit events you organize unless you are an admin or organizer.', 'error')
            return redirect(url_for('events.edit_event', event_id=event_id))
        
        # Parse dates and times
        date = dt.strptime(date_str, '%Y-%m-%d')
        exact_time = dt.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
        
        # Validate Google Maps link if provided
        valid_maps_domains = ['maps.google.com', 'www.google.com/maps', 'maps.app.goo.gl', 'goo.gl/maps']
        if google_maps_link:
            is_valid_maps_link = any(domain in google_maps_link.lower() for domain in valid_maps_domains)
            if not is_valid_maps_link:
                flash('If provided, Google Maps link must be from Google Maps (maps.google.com, www.google.com/maps, or maps.app.goo.gl).', 'error')
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
        
        # Handle event note
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
                flash(f'Cannot reduce event capacity to {new_max_attendees}. There are currently {current_attending_count} people attending. Please <a href="{edit_attendance_url}">manage attendance</a> to remove some attendees before reducing the capacity.', 'error')
                return redirect(url_for('events.edit_event', event_id=event_id))
            
            # Check for capacity increase that would allow waitlist promotion
            old_max_attendees = event.max_attendees
            if (old_max_attendees and new_max_attendees > old_max_attendees) or (not old_max_attendees and new_max_attendees):
                # Event capacity is being increased - check for waitlisted users
                available_spots = new_max_attendees - current_attending_count
                waitlisted_users = RSVP.select().where(
                    (RSVP.event == event) & (RSVP.status == 'waitlist')
                ).order_by(RSVP.created_at).limit(available_spots)
                
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
                            flash(f'Increasing capacity to {new_max_attendees} would promote {len(users_to_promote)} people from waitlist. Please use the web interface to confirm this change.', 'info')
                            return redirect(url_for('events.edit_event', event_id=event_id))

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
    
    try:
        event = Event.get_by_id(event_id)
        status = request.form.get('status')
        notes = request.form.get('notes', '')
        
        # Handle RSVP cancellation (empty status)
        if status == '' or status is None:
            try:
                rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == current_user))
                was_attending = rsvp.status == 'yes'
                rsvp.delete_instance()
                
                # If user was attending and event has capacity, promote next waitlisted user
                promoted_user = None
                if was_attending and event.max_attendees:
                    next_waitlisted = RSVP.select().where(
                        (RSVP.event == event) & (RSVP.status == 'waitlist')
                    ).order_by(RSVP.created_at).first()
                    if next_waitlisted:
                        next_waitlisted.status = 'yes'
                        next_waitlisted.updated_at = datetime.now()
                        next_waitlisted.save()
                        promoted_user = next_waitlisted.user.name
                        
                message = 'Attendance cancelled'
                if promoted_user:
                    message += f'. {promoted_user} has been moved from waitlist to attending.'
                    
                if request.headers.get('Accept') == 'application/json':
                    # Recalculate lists and counts
                    rsvp_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
                    rsvp_no_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).count()
                    rsvps = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).order_by(RSVP.created_at)
                    rsvps_no = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).order_by(RSVP.created_at)
                    rsvps_waitlist = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(RSVP.created_at)
                    from flask import render_template
                    attendees_html = render_template('events/event_detail_attendees.html', rsvps=rsvps)
                    not_attending_html = render_template('events/event_detail_not_attending.html', rsvps_no=rsvps_no)
                    waitlist_html = render_template('events/event_detail_waitlist.html', rsvps_waitlist=rsvps_waitlist)
                    capacity_pills_html = render_template('events/_capacity_pills.html', rsvp_count=rsvp_count, event=event, rsvps_waitlist=rsvps_waitlist)
                    header_pills_html = render_template('events/_header_pills.html', rsvp_count=rsvp_count, event=event, rsvps_waitlist=rsvps_waitlist, now=datetime.now())
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
        
        # Enforce event capacity and waitlist
        from peewee import fn
        rsvp_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
        # If user is already RSVP'd, update their status
        try:
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
                    next_waitlisted = RSVP.select().where(
                        (RSVP.event == event) & (RSVP.status == 'waitlist')
                    ).order_by(RSVP.created_at).first()
                    if next_waitlisted:
                        next_waitlisted.status = 'yes'
                        next_waitlisted.updated_at = datetime.now()
                        next_waitlisted.save()
                        promoted_user = next_waitlisted.user.name
                        message += f' {promoted_user} has been moved from waitlist to attending.'
        except RSVP.DoesNotExist:
            # New RSVP
            if status == 'yes' and event.max_attendees and rsvp_count >= event.max_attendees:
                rsvp = RSVP.create(
                    event=event,
                    user=current_user,
                    status='waitlist',
                    notes=notes
                )
                message = 'Event is full. You have been added to the waitlist.'
            else:
                rsvp = RSVP.create(
                    event=event,
                    user=current_user,
                    status=status,
                    notes=notes
                )
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
        capacity_pills_html = render_template('events/_capacity_pills.html', rsvp_count=rsvp_count, event=event, rsvps_waitlist=rsvps_waitlist)
        header_pills_html = render_template('events/_header_pills.html', rsvp_count=rsvp_count, event=event, rsvps_waitlist=rsvps_waitlist, now=datetime.now())
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
        if not (current_user.role == 'admin' or 
                current_user.can_organize_events() or 
                current_user.id == event.organizer_id):
            message = 'Permission denied. Only administrators, organizers, or event hosts can remove RSVPs.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
            return redirect(url_for('events.event_detail', event_id=event_id))
        
        # Find and remove the RSVP
        try:
            rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == target_user))
            prev_status = rsvp.status
            rsvp.delete_instance()
            
            # Automatic promotion disabled - manual control preferred
            # if prev_status == 'yes' and event.max_attendees:
            #     yes_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
            #     if yes_count < event.max_attendees:
            #         next_waitlisted = RSVP.select().where(
            #             (RSVP.event == event) & (RSVP.status == 'waitlist')
            #         ).order_by(RSVP.created_at).first()
            #         if next_waitlisted:
            #             next_waitlisted.status = 'yes'
            #             next_waitlisted.updated_at = datetime.now()
            #             next_waitlisted.save()
            
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
                capacity_pills_html = render_template('events/_capacity_pills.html', rsvp_count=rsvp_count, event=event, rsvps_waitlist=rsvps_waitlist)
                header_pills_html = render_template('events/_header_pills.html', rsvp_count=rsvp_count, event=event, rsvps_waitlist=rsvps_waitlist, now=datetime.now())
                
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
        if not (current_user.role == 'admin' or 
                current_user.can_organize_events() or 
                current_user.id == event.organizer_id):
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
            
            # Automatic promotion disabled - manual control preferred
            # if prev_status == 'yes' and new_status != 'yes' and event.max_attendees:
            #     yes_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
            #     if yes_count < event.max_attendees:
            #         next_waitlisted = RSVP.select().where(
            #             (RSVP.event == event) & (RSVP.status == 'waitlist')
            #         ).order_by(RSVP.created_at).first()
            #         if next_waitlisted:
            #             next_waitlisted.status = 'yes'
            #             next_waitlisted.updated_at = datetime.now()
            #             next_waitlisted.save()
            #             message += f' {next_waitlisted.user.name} was promoted from waitlist.'
            
            if request.headers.get('Accept') == 'application/json':
                # Recalculate lists and counts for real-time update
                rsvp_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count()
                rsvp_no_count = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).count()
                rsvps = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).order_by(RSVP.created_at)
                rsvps_no = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).order_by(RSVP.created_at)
                rsvps_waitlist = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'waitlist')).order_by(RSVP.created_at)
                rsvps_maybe = RSVP.select().where((RSVP.event == event) & (RSVP.status == 'maybe')).order_by(RSVP.created_at)
                
                # Check if current user can manage RSVPs
                can_manage_rsvps = (current_user.role == 'admin' or 
                                   current_user.can_organize_events() or 
                                   current_user.id == event.organizer_id)
                
                from flask import render_template
                try:
                    attendees_html = render_template('events/event_detail_attendees.html', 
                                                   rsvps=rsvps, event=event, can_manage_rsvps=can_manage_rsvps)
                    not_attending_html = render_template('events/event_detail_not_attending.html', 
                                                       rsvps_no=rsvps_no, event=event, can_manage_rsvps=can_manage_rsvps)
                    waitlist_html = render_template('events/event_detail_waitlist.html', 
                                                  rsvps_waitlist=rsvps_waitlist, event=event, can_manage_rsvps=can_manage_rsvps)
                    maybe_html = render_template('events/event_detail_maybe.html', 
                                               rsvps_maybe=rsvps_maybe, event=event, can_manage_rsvps=can_manage_rsvps)
                    capacity_pills_html = render_template('events/_capacity_pills.html', 
                                                        rsvp_count=rsvp_count, event=event, rsvps_waitlist=rsvps_waitlist)
                    header_pills_html = render_template('events/_header_pills.html', 
                                                       rsvp_count=rsvp_count, event=event, rsvps_waitlist=rsvps_waitlist, now=datetime.now())
                    
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
    rsvps_attending = list(RSVP.select().where(
        (RSVP.event == event) & (RSVP.status == 'yes')
    ).order_by(RSVP.created_at))
    
    rsvps_waitlist = list(RSVP.select().where(
        (RSVP.event == event) & (RSVP.status == 'waitlist')
    ).order_by(RSVP.created_at))
    
    rsvps_not_attending = list(RSVP.select().where(
        (RSVP.event == event) & (RSVP.status == 'no')
    ).order_by(RSVP.created_at))
    
    # Calculate counts
    rsvp_count = len(rsvps_attending)
    waitlist_count = len(rsvps_waitlist)
    not_attending_count = len(rsvps_not_attending)
    
    return render_template('events/edit_attendance.html',
                         event=event,
                         rsvps_attending=rsvps_attending,
                         rsvps_waitlist=rsvps_waitlist,
                         rsvps_not_attending=rsvps_not_attending,
                         rsvp_count=rsvp_count,
                         waitlist_count=waitlist_count,
                         not_attending_count=not_attending_count)


# Event route implementations will be moved here from app.py
# during the refactoring process
