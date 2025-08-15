"""
API routes for cosypolyamory.org

Handles JSON API endpoints for AJAX requests.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from cosypolyamory.models.user import User

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/user')
@login_required
def api_user():
    """Return current user information as JSON"""
    return jsonify({
        'id': current_user.id,
        'email': current_user.email,
        'name': current_user.name,
        'avatar_url': current_user.avatar_url,
        'provider': current_user.provider,
        'created_at': current_user.created_at.isoformat(),
        'is_approved': current_user.is_approved,
        'is_organizer': current_user.is_organizer,
        'is_admin': current_user.is_admin,
        'role': current_user.get_role_display()
    })


@bp.route('/organizers')
@login_required
def api_organizers():
    """Return list of users who can organize events"""
    try:
        # Get all users who can organize events (admins and organizers)
        organizers = User.select().where(User.role.in_(['admin', 'organizer']))
        
        organizer_list = []
        for organizer in organizers:
            organizer_list.append({
                'id': organizer.id,
                'name': organizer.name,
                'email': organizer.email,
                'role': organizer.role,
                'is_current_user': organizer.id == current_user.id
            })
        
        # Sort by name
        organizer_list.sort(key=lambda x: x['name'])
        
        return jsonify(organizer_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
