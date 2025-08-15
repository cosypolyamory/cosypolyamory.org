"""
User API endpoints

Handles general user-related API operations like search, profile data, etc.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from cosypolyamory.models.user import User

bp = Blueprint('users', __name__)


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


@bp.route('/users/search')
@login_required
def search_users():
    """Search for users by name or email (for autocomplete)"""
    try:
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 10)), 50)  # Max 50 results
        
        if not query or len(query) < 2:
            return jsonify([])
        
        # Search in name and email fields using Peewee ORM
        search_pattern = f"%{query}%"
        
        # Get users matching the search query
        users = (User.select()
                    .where((User.name.ilike(search_pattern) | User.email.ilike(search_pattern))
                           & (User.role != 'new'))
                    .order_by(User.name.asc())
                    .limit(limit))
        
        result = []
        for user in users:
            # Map role to display name
            role_display = {
                'pending': 'Pending',
                'approved': 'Member', 
                'organizer': 'Organizer',
                'admin': 'Admin',
                'rejected': 'Rejected'
            }.get(user.role, user.role.title())
            
            result.append({
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'role_display': role_display,
                'avatar_url': getattr(user, 'avatar_url', None)
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
