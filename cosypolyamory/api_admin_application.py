from flask import jsonify
from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.models.user import User
from cosypolyamory.app import app

@app.route('/api/admin/application/<int:application_id>')
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
