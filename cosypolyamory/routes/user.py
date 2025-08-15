"""User routes module for cosypolyamory application.

This module contains user-related routes including profile management, 
user interactions, and application system functionality.
"""

import os
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from cosypolyamory.models.user import User
from cosypolyamory.models.user_application import UserApplication

bp = Blueprint('user', __name__)


@bp.route('/apply')
@login_required
def apply():
    """Community application form"""
    # Check if user already has an application
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        return redirect(url_for('user.application_status'))
    except UserApplication.DoesNotExist:
        pass
    
    # Get questions from environment
    questions = {
        'question_1': os.getenv('APPLICATION_QUESTION_1', 'Question 1'),
        'question_2': os.getenv('APPLICATION_QUESTION_2', 'Question 2'),
        'question_3': os.getenv('APPLICATION_QUESTION_3', 'Question 3'),
        'question_4': os.getenv('APPLICATION_QUESTION_4', 'Question 4'),
        'question_5': os.getenv('APPLICATION_QUESTION_5', 'Question 5'),
        'question_6': os.getenv('APPLICATION_QUESTION_6', 'Question 6'),
        'question_7': os.getenv('APPLICATION_QUESTION_7', 'Question 7'),
    }
    
    return render_template('user/apply.html', questions=questions)


@bp.route('/apply', methods=['POST'])
@login_required
def submit_application():
    """Submit community application"""
    # Check if user already has an application
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        flash('You have already submitted an application.', 'info')
        return redirect(url_for('user.application_status'))
    except UserApplication.DoesNotExist:
        pass
    
    # Create application
    application = UserApplication.create(
        user=current_user,
        question_1_answer=request.form.get('question_1', ''),
        question_2_answer=request.form.get('question_2', ''),
        question_3_answer=request.form.get('question_3', ''),
        question_4_answer=request.form.get('question_4', ''),
        question_5_answer=request.form.get('question_5', ''),
        question_6_answer=request.form.get('question_6', ''),
        question_7_answer=request.form.get('question_7', ''),
    )
    # Set user role to 'pending' after application submission
    current_user.role = 'pending'
    current_user.save()
    flash('Your application has been submitted! You will be notified once it has been reviewed.', 'success')
    return redirect(url_for('user.application_status'))


@bp.route('/application-status')
@login_required
def application_status():
    """Show user's application status"""
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        return render_template('user/application_status.html', application=application)
    except UserApplication.DoesNotExist:
        return redirect(url_for('user.apply'))
