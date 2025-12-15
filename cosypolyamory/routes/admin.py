"""
Admin routes for cosypolyamory.org

Handles administrative interface and management functionality.
"""

import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from cosypolyamory.models.user import User
from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.models.event_note import EventNote
from cosypolyamory.models.event import Event
from cosypolyamory.database import database
from cosypolyamory.decorators import organizer_required, admin_or_organizer_required
from cosypolyamory.notification import notify_application_approved, notify_application_rejected

bp = Blueprint('admin', __name__, url_prefix='/admin')

# Moderation Routes
@bp.route('/moderate')
@organizer_required
def moderate_applications():
    """Application review queue - only show pending applications with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get paginated pending applications (applications from users with pending/new status)
    pending_applications_query = (UserApplication.select()
                                 .join(User)
                                 .where(User.role == "pending")
                                 .order_by(UserApplication.submitted_at))
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
    
    return render_template('admin/moderate.html',
                         pending_applications=pending_applications,
                         pending_count=total_applications,
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

@bp.route('/moderate/<int:application_id>/approve', methods=['POST'])
@organizer_required
def approve_application(application_id):
    """Approve a user application"""
    try:
        with database.atomic():
            application = UserApplication.get_by_id(application_id)
            application.reviewed_at = datetime.now()
            application.reviewed_by = current_user
            application.review_notes = request.form.get('notes', '')
            application.save()
            
            # Update user status
            user = application.user
            user.role = 'approved'
            user.is_approved = True
            user.save()
            
        # Send approval email notification
        try:
            notify_application_approved(user)
            flash(f'Application for {user.name} has been approved and notification email sent.', 'success')
        except Exception as email_error:
            flash(f'Application for {user.name} has been approved, but email notification failed: {str(email_error)}', 'warning')
            
    except Exception as e:
        flash(f'Error approving application: {str(e)}', 'error')
    
    return redirect(url_for('admin.moderate_applications'))

@bp.route('/moderate/<int:application_id>/reject', methods=['POST'])
@organizer_required
def reject_application(application_id):
    """Reject a user application"""
    try:
        with database.atomic():
            application = UserApplication.get_by_id(application_id)
            application.reviewed_at = datetime.now()
            application.reviewed_by = current_user
            application.review_notes = request.form.get('admin_notes', '')
            application.save()

            # Update user status
            user = application.user
            user.role = "rejected"
            user.is_approved = False
            user.save()
            
        # Send rejection email notification with reason
        try:
            notify_application_rejected(user, rejection_reason=application.review_notes)
            flash(f'Application for {application.user.name} has been rejected and notification email sent.', 'info')
        except Exception as email_error:
            flash(f'Application for {application.user.name} has been rejected, but email notification failed: {str(email_error)}', 'warning')
            
    except UserApplication.DoesNotExist:
        flash('Application not found.', 'error')
    except Exception as e:
        flash(f'Error rejecting application: {str(e)}', 'error')
    
    return redirect(url_for('admin.moderate_applications'))

# Admin Dashboard
@bp.route('/')
@admin_or_organizer_required
def admin_dashboard():
    """Admin dashboard"""
    users = list(User.select())
    
    # Calculate pending applications count for the notification message
    pending_applications_count = (UserApplication.select()
                                 .join(User)
                                 .where(User.role == "pending")
                                 .count())
    
    return render_template('admin/admin.html', 
                         users=users, 
                         pending_applications_count=pending_applications_count)

# Event Notes Admin Routes (admins and organizers only)
@bp.route('/event-notes')
@admin_or_organizer_required
def event_notes():
    notes = EventNote.select().order_by(EventNote.name)
    return render_template('events/event_notes.html', event_notes=notes)

@bp.route('/event-notes/add', methods=['GET', 'POST'])
@admin_or_organizer_required
def add_event_note():
    
    if request.method == 'POST':
        try:
            with database.atomic():
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
                return redirect(url_for('admin.event_notes'))
        except Exception as e:
            flash(f'Error adding event note: {str(e)}', 'error')
            return render_template('events/add_event_note.html')

    return render_template('events/add_event_note.html')

@bp.route('/event-notes/<int:note_id>/edit', methods=['GET', 'POST'])
@admin_or_organizer_required
def edit_event_note(note_id):
    try:
        note = EventNote.get_by_id(note_id)
    except EventNote.DoesNotExist:
        flash('Event note not found.', 'error')
        return redirect(url_for('admin.event_notes'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        note_text = request.form.get('note', '').strip()
        if not name or not note_text:
            flash('Both name and note are required.', 'error')
            return render_template('events/edit_event_note.html', note=note)
        
        try:
            with database.atomic():
                # Check for duplicate name (excluding self)
                if EventNote.select().where((EventNote.name == name) & (EventNote.id != note.id)).exists():
                    flash('A note with this name already exists.', 'error')
                    return render_template('events/edit_event_note.html', note=note)
                
                note.name = name
                note.note = note_text
                note.save()
                
            flash('Event note updated successfully.', 'success')
            return redirect(url_for('admin.event_notes'))
        except Exception as e:
            flash(f'Error updating event note: {str(e)}', 'error')
            return render_template('events/edit_event_note.html', note=note)
            
    return render_template('events/edit_event_note.html', note=note)

@bp.route('/event-notes/<int:note_id>/delete', methods=['POST'])
@admin_or_organizer_required
def delete_event_note(note_id):
    try:
        note = EventNote.get_by_id(note_id)
    except EventNote.DoesNotExist:
        flash('Event note not found.', 'error')
        return redirect(url_for('admin.event_notes'))
    
    try:
        with database.atomic():
            # Check if the note is being used by any events
            from cosypolyamory.models.event import Event
            events_using_note = list(Event.select().where(Event.event_note == note))
            
            if events_using_note:
                event_titles = [event.title for event in events_using_note]
                flash(f'Cannot delete note "{note.name}" because it is being used by the following events: {", ".join(event_titles)}', 'error')
                return redirect(url_for('admin.event_notes'))
            
            # Safe to delete
            note_name = note.name
            note.delete_instance()
            
        flash(f'Event note "{note_name}" has been deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting event note: {str(e)}', 'error')
        
    return redirect(url_for('admin.event_notes'))

@bp.route('/community-insights')
@organizer_required
def community_insights():
    """Community statistics and insights for organizers/admins"""
    try:
        from cosypolyamory.models.user import User
        from datetime import timedelta
        
        # Get all approved users with pronouns
        approved_users = (User
                         .select()
                         .where(
                             (User.role.in_(['approved', 'admin', 'organizer'])) &
                             (User.pronouns.is_null(False))
                         ))
        
        # Calculate pronoun statistics for all approved users
        # Extract first two words only for graphing (e.g., "they/them" from "they/them/theirs")
        # Normalize to lowercase for consistent grouping
        pronoun_counts = {}
        
        for user in approved_users:
            if user.pronouns:
                pronouns = user.pronouns.strip().lower()
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
        
        # Get total user counts by role
        total_approved = User.select().where(User.role == 'approved').count()
        total_organizers = User.select().where(User.role == 'organizer').count()
        total_admins = User.select().where(User.role == 'admin').count()
        total_pending = User.select().where(User.role == 'pending').count()
        total_users_with_pronouns = approved_users.count()
        
        community_stats = {
            'total_approved': total_approved,
            'total_organizers': total_organizers, 
            'total_admins': total_admins,
            'total_pending': total_pending,
            'total_users_with_pronouns': total_users_with_pronouns,
            'total_community_members': total_approved + total_organizers + total_admins
        }
        
        # Calculate user growth statistics - get all time data
        # We'll calculate monthly data points from the earliest user to now
        user_growth_data = []
        today = datetime.now().date()
        
        # Find the earliest user creation date
        earliest_user = User.select(User.created_at).order_by(User.created_at.asc()).first()
        if earliest_user and earliest_user.created_at:
            earliest_date = earliest_user.created_at
            # Calculate how many months to go back (only to when data exists)
            months_diff = (today.year - earliest_date.year) * 12 + (today.month - earliest_date.month)
            max_months = months_diff  # Only go back to when data exists
        else:
            max_months = 0  # No users, just show current month
        
        # Go back to earliest data, month by month
        for months_ago in range(max_months, -1, -1):
            # Calculate the date for this data point (end of month)
            if months_ago == 0:
                # Current month - use today
                cutoff_date = datetime.now()
                month_label = cutoff_date.strftime('%b %Y')
            else:
                # Previous months - use first day of that many months ago
                year = today.year
                month = today.month - months_ago
                while month <= 0:
                    month += 12
                    year -= 1
                cutoff_date = datetime(year, month, 1)
                month_label = cutoff_date.strftime('%b %Y')
            
            # Total registered users (all users created before cutoff)
            total_registered = User.select().where(
                User.created_at <= cutoff_date
            ).count()
            
            # Total users with applications submitted
            total_with_applications = User.select().where(
                (User.created_at <= cutoff_date) &
                (User.role.in_(['pending', 'approved', 'organizer', 'admin', 'rejected']))
            ).count()
            
            # Total approved users (approved, organizer, admin roles)
            total_approved_at_date = User.select().where(
                (User.created_at <= cutoff_date) &
                (User.role.in_(['approved', 'organizer', 'admin']))
            ).count()
            
            # Active users (logged in within last 2 weeks from cutoff date)
            two_weeks_before_cutoff = cutoff_date - timedelta(days=14)
            active_users = User.select().where(
                (User.created_at <= cutoff_date) &
                (User.last_login >= two_weeks_before_cutoff) &
                (User.last_login <= cutoff_date)
            ).count()
            
            user_growth_data.append({
                'month': month_label,
                'total_registered': total_registered,
                'total_with_applications': total_with_applications,
                'total_approved': total_approved_at_date,
                'active_users': active_users
            })
        
        # Calculate attendance and hosting statistics
        from cosypolyamory.models.rsvp import RSVP
        from cosypolyamory.models.no_show import NoShow
        from peewee import fn
        
        # Top Attendees: Users with most "yes" RSVPs to past events (excluding events they hosted/co-hosted)
        top_attendees_query = (User
            .select(User, fn.COUNT(RSVP.id).alias('attendance_count'))
            .join(RSVP, on=(User.id == RSVP.user))
            .join(Event, on=(RSVP.event == Event.id))
            .where(
                (User.role.in_(['approved', 'admin', 'organizer'])) &
                (RSVP.status == 'yes') &
                (Event.exact_time < datetime.now()) &  # Only count past events
                (Event.organizer != User.id) &  # Exclude events they organized
                ((Event.co_host.is_null(True)) | (Event.co_host != User.id))  # Exclude events they co-hosted
            )
            .group_by(User.id)
            .order_by(fn.COUNT(RSVP.id).desc())
            .limit(10))
        
        top_attendees = []
        try:
            for user_data in top_attendees_query:
                top_attendees.append({
                    'name': user_data.name,
                    'count': user_data.attendance_count,
                    'role': user_data.role
                })
        except Exception as e:
            print(f"Error calculating top attendees: {e}")
        
        # Top Organizers: Users who have hosted/co-hosted the most past events
        # Count both organizing and co-hosting as equal
        from peewee import Case, JOIN
        
        # Query for organizers (main hosts)
        organizer_counts = (User
            .select(User.id, User.name, User.role, fn.COUNT(Event.id).alias('host_count'))
            .join(Event, on=(User.id == Event.organizer))
            .where(Event.exact_time < datetime.now())  # Only past events
            .group_by(User.id, User.name, User.role))
        
        # Query for co-hosts  
        cohost_counts = (User
            .select(User.id, User.name, User.role, fn.COUNT(Event.id).alias('host_count'))
            .join(Event, on=(User.id == Event.co_host))
            .where(Event.exact_time < datetime.now())  # Only past events
            .group_by(User.id, User.name, User.role))
        
        # Combine and sum the counts
        top_organizers = []
        try:
            # Build a dictionary to combine organizer and co-host counts
            host_stats = {}
            
            # Add organizer counts
            for user_data in organizer_counts:
                user_id = user_data.id
                if user_id not in host_stats:
                    host_stats[user_id] = {
                        'name': user_data.name,
                        'role': user_data.role,
                        'count': 0
                    }
                host_stats[user_id]['count'] += user_data.host_count
            
            # Add co-host counts
            for user_data in cohost_counts:
                user_id = user_data.id
                if user_id not in host_stats:
                    host_stats[user_id] = {
                        'name': user_data.name,
                        'role': user_data.role,
                        'count': 0
                    }
                host_stats[user_id]['count'] += user_data.host_count
            
            # Sort and limit to top 10
            top_organizers = sorted(host_stats.values(), key=lambda x: x['count'], reverse=True)[:10]
        except Exception as e:
            print(f"Error calculating top organizers: {e}")
        
        # Top Flakes: Users with most no-shows (unchanged)
        top_flakes_query = (User
            .select(User, fn.COUNT(NoShow.id).alias('noshow_count'))
            .join(NoShow, on=(User.id == NoShow.user))
            .where(User.role.in_(['approved', 'admin', 'organizer']))
            .group_by(User.id)
            .order_by(fn.COUNT(NoShow.id).desc())
            .limit(10))
        
        top_flakes = []
        try:
            for user_data in top_flakes_query:
                top_flakes.append({
                    'name': user_data.name,
                    'count': user_data.noshow_count,
                    'role': user_data.role
                })
        except Exception as e:
            print(f"Error calculating top flakes: {e}")
        
    except Exception as e:
        print(f"Error calculating community statistics: {e}")
        pronoun_stats = {'pronouns': {}}
        community_stats = {}
        top_attendees = []
        top_organizers = []
        top_flakes = []
        user_growth_data = []
    
    return render_template('admin/community_insights.html',
                           pronoun_stats=pronoun_stats,
                           community_stats=community_stats,
                           top_attendees=top_attendees,
                           top_organizers=top_organizers,
                           top_flakes=top_flakes,
                           user_growth_data=user_growth_data)
