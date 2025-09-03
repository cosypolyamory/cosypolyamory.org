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
    # Check if user already has an application
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        return redirect(url_for('auth.profile'))
    except UserApplication.DoesNotExist:
        pass
    
    # Get questions from environment
    questions = {
        'question_1': os.getenv('QUESTION_1', 'Question 1'),
        'question_2': os.getenv('QUESTION_2', 'Question 2'),
        'question_3': os.getenv('QUESTION_3', 'Question 3'),
        'question_4': os.getenv('QUESTION_4', 'Question 4'),
        'question_5': os.getenv('QUESTION_5', 'Question 5'),
        'question_6': os.getenv('QUESTION_6', 'Question 6'),
        'question_7': os.getenv('QUESTION_7', 'Question 7'),
    }
    
    # Get character limits from environment
    character_limits = {}
    for i in range(1, 8):
        limit_config = os.getenv(f'QUESTION_{i}_MINMAX_CHARACTERS', '100_1000')
        try:
            min_chars, max_chars = limit_config.split('_')
            character_limits[f'question_{i}'] = {
                'min': int(min_chars),
                'max': int(max_chars)
            }
        except (ValueError, IndexError):
            # Default values if parsing fails
            character_limits[f'question_{i}'] = {'min': 100, 'max': 1000}
    
    return render_template('user/apply.html', questions=questions, character_limits=character_limits)


@bp.route('/apply', methods=['POST'])
@login_required
def submit_application():
    """Submit community application"""
    # Check if user already has an application
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        flash('You have already submitted an application.', 'info')
        return redirect(url_for('auth.profile'))
    except UserApplication.DoesNotExist:
        pass
    
    # Validate character limits
    character_limits = {}
    for i in range(1, 8):
        limit_config = os.getenv(f'QUESTION_{i}_MINMAX_CHARACTERS', '100_1000')
        try:
            min_chars, max_chars = limit_config.split('_')
            character_limits[f'question_{i}'] = {
                'min': int(min_chars),
                'max': int(max_chars)
            }
        except (ValueError, IndexError):
            character_limits[f'question_{i}'] = {'min': 100, 'max': 1000}
    
    # Validate each answer
    validation_errors = []
    answers = {}
    for i in range(1, 8):
        answer = request.form.get(f'question_{i}', '').strip()
        answers[f'question_{i}_answer'] = answer
        
        limits = character_limits[f'question_{i}']
        if len(answer) < limits['min']:
            validation_errors.append(f'Question {i} must be at least {limits["min"]} characters long.')
        elif len(answer) > limits['max']:
            validation_errors.append(f'Question {i} must not exceed {limits["max"]} characters.')
    
    if validation_errors:
        for error in validation_errors:
            flash(error, 'error')
        # Preserve form data on validation error
        form_data = {
            'question_1': request.form.get('question_1', ''),
            'question_2': request.form.get('question_2', ''),
            'question_3': request.form.get('question_3', ''),
            'question_4': request.form.get('question_4', ''),
            'question_5': request.form.get('question_5', ''),
            'question_6': request.form.get('question_6', ''),
            'question_7': request.form.get('question_7', ''),
        }
        # Get questions for the template
        questions = {
            'question_1': os.getenv('QUESTION_1', 'Question 1'),
            'question_2': os.getenv('QUESTION_2', 'Question 2'),
            'question_3': os.getenv('QUESTION_3', 'Question 3'),
            'question_4': os.getenv('QUESTION_4', 'Question 4'),
            'question_5': os.getenv('QUESTION_5', 'Question 5'),
            'question_6': os.getenv('QUESTION_6', 'Question 6'),
            'question_7': os.getenv('QUESTION_7', 'Question 7'),
        }
        return render_template('user/apply.html', questions=questions, character_limits=character_limits, form_data=form_data)
    
    # Create application and update user status in a transaction
    try:
        with database.atomic():
            # Create application
            application = UserApplication.create(
                user=current_user,
                **answers
            )
            # Set user role to 'pending' after application submission
            current_user.role = 'pending'
            current_user.save()
            
        flash('Your application has been submitted! You will be notified once it has been reviewed.', 'success')
        return redirect(url_for('auth.profile'))
    except Exception as e:
        flash(f'Error submitting application: {str(e)}', 'error')
        # Preserve form data on error
        form_data = {
            'question_1': request.form.get('question_1', ''),
            'question_2': request.form.get('question_2', ''),
            'question_3': request.form.get('question_3', ''),
            'question_4': request.form.get('question_4', ''),
            'question_5': request.form.get('question_5', ''),
            'question_6': request.form.get('question_6', ''),
            'question_7': request.form.get('question_7', ''),
        }
        return render_template('user/apply.html', character_limits=character_limits, form_data=form_data)