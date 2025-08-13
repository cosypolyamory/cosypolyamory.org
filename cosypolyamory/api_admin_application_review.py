from flask import request, jsonify
from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.models.user import User
from cosypolyamory.app import app
from flask_login import current_user
from datetime import datetime

@app.route('/api/admin/application/<int:application_id>/review', methods=['POST'])
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
            application.status = 'approved'
            user.role = 'approved'
        else:
            application.status = 'rejected'
            user.role = 'rejected'
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
