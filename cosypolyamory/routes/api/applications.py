"""
Application API endpoints

Handles application review and management API operations.
"""

import os
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import current_user

from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.models.user import User

bp = Blueprint('applications', __name__)


def admin_required(f):
    """Decorator to require admin role"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_organize_events():
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/admin/application-questions')
@admin_required
def api_admin_application_questions():
    """Return the application questions"""
    questions = [
        os.getenv('APPLICATION_QUESTION_1', 'Question 1'),
        os.getenv('APPLICATION_QUESTION_2', 'Question 2'),
        os.getenv('APPLICATION_QUESTION_3', 'Question 3'),
        os.getenv('APPLICATION_QUESTION_4', 'Question 4'),
        os.getenv('APPLICATION_QUESTION_5', 'Question 5'),
        os.getenv('APPLICATION_QUESTION_6', 'Question 6'),
        os.getenv('APPLICATION_QUESTION_7', 'Question 7'),
    ]
    return jsonify({'success': True, 'questions': questions})


@bp.route('/admin/application/<int:application_id>')
@admin_required
def api_admin_application(application_id):
    """Return application details for admin modal review"""
    try:
        application = UserApplication.get_by_id(application_id)
        user = application.user
        data = {
            'id': application.id,
            'user_id': user.id,
            'user_name': user.name,
            'user_email': user.email,
            'status': application.status,
            'submitted_at': application.submitted_at.isoformat(),
            'reviewed_at': application.reviewed_at.isoformat() if application.reviewed_at else None,
            'reviewed_by': application.reviewed_by.name if application.reviewed_by else None,
            'review_notes': application.review_notes,
            'answers': [
                application.question_1_answer,
                application.question_2_answer,
                application.question_3_answer,
                application.question_4_answer,
                application.question_5_answer,
                application.question_6_answer,
                application.question_7_answer,
            ]
        }
        return jsonify({'success': True, 'application': data})
    except UserApplication.DoesNotExist:
        return jsonify({'success': False, 'error': 'Application not found'}), 404


@bp.route('/admin/application/<int:application_id>/review', methods=['POST'])
@admin_required
def api_admin_application_review(application_id):
    """Accept or reject an application"""
    data = request.get_json()
    action = data.get('action')
    notes = data.get('notes', '')
    
    if action not in ['accept', 'reject']:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    try:
        application = UserApplication.get_by_id(application_id)
        user = application.user
        
        if action == 'accept':
            user.role = 'approved'
            user.is_approved = True
        else:
            user.role = 'rejected'
            user.is_approved = False
        
        application.reviewed_at = datetime.now()
        application.reviewed_by = current_user if hasattr(current_user, 'id') else None
        application.review_notes = notes
        application.save()
        user.save()
        
        return jsonify({'success': True})
    except UserApplication.DoesNotExist:
        return jsonify({'success': False, 'error': 'Application not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/admin/application/user/<user_id>')
@admin_required
def api_admin_application_by_user(user_id):
    """Get application details by user ID"""
    try:
        user = User.get_by_id(user_id)
        application = UserApplication.select().where(UserApplication.user == user).order_by(UserApplication.submitted_at.desc()).first()
        
        if not application:
            return jsonify({'success': False, 'error': 'No application found for this user'})
        
        data = {
            'id': application.id,
            'user_id': user.id,
            'user_name': user.name,
            'user_email': user.email,
            'status': application.status,
            'submitted_at': application.submitted_at.isoformat(),
            'reviewed_at': application.reviewed_at.isoformat() if application.reviewed_at else None,
            'reviewed_by': application.reviewed_by.name if application.reviewed_by else None,
            'review_notes': application.review_notes,
            'answers': [
                application.question_1_answer,
                application.question_2_answer,
                application.question_3_answer,
                application.question_4_answer,
                application.question_5_answer,
                application.question_6_answer,
                application.question_7_answer,
            ]
        }
        return jsonify({'success': True, 'application': data})
    except User.DoesNotExist:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
