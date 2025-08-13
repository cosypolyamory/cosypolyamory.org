from flask import jsonify
from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.models.user import User
from cosypolyamory.app import app

@app.route('/api/admin/application/user/<user_id>')
def api_admin_application_by_user(user_id):
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
