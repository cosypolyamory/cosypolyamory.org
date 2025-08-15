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

import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from cosypolyamory.models.event import Event
from cosypolyamory.models.rsvp import RSVP
from cosypolyamory.models.user import User
from cosypolyamory.models.event_note import EventNote

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


def extract_google_maps_info(maps_link):
    """Extract latitude/longitude from Google Maps link if possible"""
    # This function should be imported or defined elsewhere
    # For now, return None to avoid errors
    return None


@bp.route('/')
def events_list():
    """List all events with appropriate visibility"""
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
                         now=datetime.now())


@bp.route('/<int:event_id>')
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
        return redirect(url_for('events.events_list'))


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
    return render_template('events/create_event.html', organizers=organizer_list, event_notes=event_notes)


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
            return redirect(url_for('events.event_detail', event_id=event_id))
        
        if status not in ['yes', 'no', 'maybe']:
            message = 'Invalid attendance status.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
            return redirect(url_for('events.event_detail', event_id=event_id))
        
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
        
        return redirect(url_for('events.event_detail', event_id=event_id))
        
    except Event.DoesNotExist:
        message = 'Event not found.'
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('events.events_list'))

# Event route implementations will be moved here from app.py
# during the refactoring process
