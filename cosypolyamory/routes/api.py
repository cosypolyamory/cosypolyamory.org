"""
API routes for cosypolyamory.org

Handles JSON API endpoints for AJAX requests.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

bp = Blueprint('api', __name__, url_prefix='/api')

# The actual route implementations will be moved here from app.py
# during the refactoring process

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
