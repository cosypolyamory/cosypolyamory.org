"""User routes module for cosypolyamory application.

This module contains user-related routes including profile management, 
user interactions, and application system functionality.
"""

import os
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from cosypolyamory.models.user import User
from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.database import database

bp = Blueprint('user', __name__)


@bp.route('/apply')
@login_required
def apply():
    """Community application form"""
    # Special handling for users marked as 'new' - they should start fresh
    if current_user.role == 'new':
        # Clean up any stale application data for users marked as 'new'
        try:
            stale_application = UserApplication.get(UserApplication.user == current_user)
            stale_application.delete_instance()
            from flask import current_app
            current_app.logger.warning(f"Deleted stale application for user {current_user.id} marked as 'new'")
        except UserApplication.DoesNotExist:
            pass  # Good, no stale data
    
    # Check if user already has an application
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        return redirect(url_for('auth.profile'))
    except UserApplication.DoesNotExist:
        pass
    
    # Get questions from environment dynamically
    questions = UserApplication.get_questions_from_env()
    
    # Get character limits from environment
    character_limits = {}
    for i, question_key in enumerate(questions.keys(), 1):
        limit_config = os.getenv(f'QUESTION_{i}_MINMAX_CHARACTERS', '100_1000')
        try:
            min_chars, max_chars = limit_config.split('_')
            character_limits[question_key] = {
                'min': int(min_chars),
                'max': int(max_chars)
            }
        except (ValueError, IndexError):
            # Default values if parsing fails
            character_limits[question_key] = {'min': 100, 'max': 1000}
    
    return render_template('user/apply.html', questions=questions, character_limits=character_limits)


@bp.route('/apply', methods=['POST'])
@login_required
def submit_application():
    """Submit community application"""
    # Special handling for users marked as 'new' - they should start fresh
    if current_user.role == 'new':
        # Clean up any stale application data for users marked as 'new'
        try:
            stale_application = UserApplication.get(UserApplication.user == current_user)
            stale_application.delete_instance()
            from flask import current_app
            current_app.logger.warning(f"Deleted stale application for user {current_user.id} marked as 'new' during submission")
        except UserApplication.DoesNotExist:
            pass  # Good, no stale data
    
    # Check if user already has an application
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        flash('You have already submitted an application.', 'info')
        return redirect(url_for('auth.profile'))
    except UserApplication.DoesNotExist:
        pass
    
    # Get questions from environment dynamically
    questions = UserApplication.get_questions_from_env()
    
    # Validate character limits
    character_limits = {}
    for i, question_key in enumerate(questions.keys(), 1):
        limit_config = os.getenv(f'QUESTION_{i}_MINMAX_CHARACTERS', '100_1000')
        try:
            min_chars, max_chars = limit_config.split('_')
            character_limits[question_key] = {
                'min': int(min_chars),
                'max': int(max_chars)
            }
        except (ValueError, IndexError):
            character_limits[question_key] = {'min': 100, 'max': 1000}
    
    # Validate each answer
    validation_errors = []
    answers = {}
    for i, question_key in enumerate(questions.keys(), 1):
        answer = request.form.get(question_key, '').strip()
        answers[question_key] = answer
        
        limits = character_limits[question_key]
        if len(answer) < limits['min']:
            validation_errors.append(f'Question {i} must be at least {limits["min"]} characters long.')
        elif len(answer) > limits['max']:
            validation_errors.append(f'Question {i} must not exceed {limits["max"]} characters.')
    
    if validation_errors:
        for error in validation_errors:
            flash(error, 'error')
        # Preserve form data on validation error
        form_data = {}
        for question_key in questions.keys():
            form_data[question_key] = request.form.get(question_key, '')
        
        return render_template('user/apply.html', questions=questions, character_limits=character_limits, form_data=form_data)
    
    # Create application and update user status in a transaction
    try:
        with database.atomic():
            # Create application with questions and answers stored together
            application = UserApplication.create(user=current_user)
            
            # Store both questions and answers from the current .env state
            qa_data = {}
            for question_key, question_text in questions.items():
                qa_data[question_key] = {
                    'question': question_text,
                    'answer': answers[question_key]
                }
            application.set_questions_and_answers(qa_data)
            application.save()
            
            # Set user role to 'pending' after application submission
            current_user.role = 'pending'
            current_user.save()
            
        flash('Your application has been submitted! You will be notified once it has been reviewed.', 'success')
        return redirect(url_for('auth.profile'))
    except Exception as e:
        flash(f'Error submitting application: {str(e)}', 'error')
        # Preserve form data on error
        form_data = {}
        for question_key in questions.keys():
            form_data[question_key] = request.form.get(question_key, '')
        
        return render_template('user/apply.html', questions=questions, character_limits=character_limits, form_data=form_data)