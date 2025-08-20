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
from cosypolyamory.decorators import organizer_required, admin_or_organizer_required

bp = Blueprint('admin', __name__, url_prefix='/admin')

# Moderation Routes
@bp.route('/moderate')
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

@bp.route('/moderate/<int:application_id>/approve', methods=['POST'])
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
    
    return redirect(url_for('admin.moderate_applications'))

@bp.route('/moderate/<int:application_id>/reject', methods=['POST'])
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
    
    return redirect(url_for('admin.moderate_applications'))

# Admin Dashboard
@bp.route('/')
@admin_or_organizer_required
def admin_dashboard():
    """Admin dashboard"""
    users = list(User.select())
    return render_template('admin/admin.html', users=users)

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
        # Check for duplicate name (excluding self)
        if EventNote.select().where((EventNote.name == name) & (EventNote.id != note.id)).exists():
            flash('A note with this name already exists.', 'error')
            return render_template('events/edit_event_note.html', note=note)
        note.name = name
        note.note = note_text
        note.save()
        flash('Event note updated successfully.', 'success')
        return redirect(url_for('admin.event_notes'))
    return render_template('events/edit_event_note.html', note=note)

@bp.route('/event-notes/<int:note_id>/delete', methods=['POST'])
@admin_or_organizer_required
def delete_event_note(note_id):
    try:
        note = EventNote.get_by_id(note_id)
    except EventNote.DoesNotExist:
        flash('Event note not found.', 'error')
        return redirect(url_for('admin.event_notes'))
    
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
    return redirect(url_for('admin.event_notes'))
