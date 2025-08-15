"""
Shared decorators for cosypolyamory.org

Common authentication and authorization decorators used across blueprints.
"""

from functools import wraps
from flask import redirect, url_for, flash, request, jsonify
from flask_login import current_user


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        # Check if user has admin status in database
        if not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('pages.index'))
        return f(*args, **kwargs)
    return decorated_function


def organizer_required(f):
    """Decorator to require organizer access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.can_organize_events():
            flash('Organizer access required.', 'error')
            return redirect(url_for('pages.index'))
        return f(*args, **kwargs)
    return decorated_function


def admin_or_organizer_required(f):
    """Decorator to require admin or organizer access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.can_organize_events():
            flash('Admin or Organizer access required.', 'error')
            return redirect(url_for('pages.index'))
        return f(*args, **kwargs)
    return decorated_function


def approved_user_required(f):
    """Decorator to require approved user status"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': 'Please log in to continue.'})
            return redirect(url_for('auth.login'))
        if current_user.role not in ['approved', 'admin', 'organizer']:
            message = 'Community approval required to access this feature.'
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': message})
            flash(message, 'info')
            return redirect(url_for('user.application_status'))
        return f(*args, **kwargs)
    return decorated_function
