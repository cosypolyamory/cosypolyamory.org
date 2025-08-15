"""
Authentication routes for cosypolyamory.org

Handles OAuth login, logout, and profile management.
"""

import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user

bp = Blueprint('auth', __name__)

# Note: OAuth clients (google, github, reddit) need to be imported in app.py


@bp.route('/login')
def login():
    """Display login page with OAuth providers"""
    return render_template('user/login.html')


@bp.route('/login/<provider>')
def oauth_login(provider):
    """Initiate OAuth login with specified provider"""
    from flask import current_app
    
    # Get OAuth instance from app extensions
    oauth = current_app.extensions.get('authlib.integrations.flask_client')
    if not oauth:
        flash('OAuth not configured properly', 'error')
        return redirect(url_for('auth.login'))
    
    print(f"Attempting to login with {provider}")
    if provider == 'google':
        redirect_uri = url_for('auth.oauth_callback', provider='google', _external=True)
        print(f"Google redirect URI: {redirect_uri}")
        return oauth.google.authorize_redirect(redirect_uri)
    elif provider == 'github':
        redirect_uri = url_for('auth.oauth_callback', provider='github', _external=True)
        print(f"GitHub redirect URI: {redirect_uri}")
        print(f"GitHub client ID: {os.getenv('GITHUB_CLIENT_ID')}")
        return oauth.github.authorize_redirect(redirect_uri)
    elif provider == 'reddit':
        redirect_uri = url_for('auth.oauth_callback', provider='reddit', _external=True)
        print(f"Reddit redirect URI: {redirect_uri}")
        # Reddit requires a unique state parameter for security
        return oauth.reddit.authorize_redirect(redirect_uri, duration='permanent')
    else:
        flash('Unknown OAuth provider', 'error')
        return redirect(url_for('auth.login'))


@bp.route('/callback/<provider>')
def oauth_callback(provider):
    """Handle OAuth callback and create user session"""
    from flask import current_app
    from cosypolyamory.models.user import User
    
    # Get OAuth instance from app extensions
    oauth = current_app.extensions.get('authlib.integrations.flask_client')
    if not oauth:
        flash('OAuth not configured properly', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        print(f"Processing callback for {provider}")
        if provider == 'google':
            token = oauth.google.authorize_access_token()
            print(f"Google token received: {type(token)}")
            # Get user info from Google API
            resp = oauth.google.get('userinfo', token=token)
            user_info = resp.json()
            print(f"Google user_info: {user_info}")
            if user_info and isinstance(user_info, dict):
                user_id = f"google_{user_info['id']}"
                user = User(
                    user_id=user_id,
                    email=user_info['email'],
                    name=user_info['name'],
                    avatar_url=user_info.get('picture'),
                    provider='google'
                )
            else:
                raise Exception("Invalid user info received from Google")
        elif provider == 'github':
            token = oauth.github.authorize_access_token()
            print(f"GitHub token received: {type(token)}")
            resp = oauth.github.get('user', token=token)
            user_info = resp.json()
            print(f"GitHub user_info: {user_info}")
            
            # Check if user_info is valid
            if not isinstance(user_info, dict) or 'id' not in user_info:
                raise Exception(f"Invalid user info received from GitHub: {user_info}")
            
            # Get user email (may require additional API call)
            primary_email = user_info.get('email')  # Try to get email from user info first
            if not primary_email:
                try:
                    email_resp = oauth.github.get('user/emails', token=token)
                    emails = email_resp.json()
                    print(f"GitHub emails: {emails}")
                    if isinstance(emails, list) and len(emails) > 0:
                        primary_email = next((email['email'] for email in emails if email.get('primary')), 
                                           emails[0].get('email') if emails[0] else None)
                except Exception as e:
                    print(f"Error getting GitHub emails: {e}")
                    # If we can't get email, we'll use the username as a fallback
                    primary_email = f"{user_info['login']}@github.local"
            
            user_id = f"github_{user_info['id']}"
            user = User(
                user_id=user_id,
                email=primary_email,
                name=user_info.get('name') or user_info.get('login'),
                avatar_url=user_info.get('avatar_url'),
                provider='github'
            )
        elif provider == 'reddit':
            token = oauth.reddit.authorize_access_token()
            print(f"Reddit token received: {type(token)}")
            
            # Get user info from Reddit API
            resp = oauth.reddit.get('api/v1/me', token=token)
            user_info = resp.json()
            print(f"Reddit user_info: {user_info}")
            
            # Check if user_info is valid
            if not isinstance(user_info, dict) or 'id' not in user_info:
                raise Exception(f"Invalid user info received from Reddit: {user_info}")
            
            user_id = f"reddit_{user_info['id']}"
            # Reddit doesn't provide email by default, use constructed email
            constructed_email = f"{user_info['name']}@reddit.local"
            
            user = User(
                user_id=user_id,
                email=constructed_email,
                name=user_info['name'],
                avatar_url=user_info.get('icon_img', '').split('?')[0] if user_info.get('icon_img') else None,  # Clean up Reddit avatar URL
                provider='reddit'
            )
        else:
            flash('Unknown OAuth provider', 'error')
            return redirect(url_for('auth.login'))
        
        # Store user in database and login
        try:
            # Try to get existing user or create new one
            try:
                user = User.get(User.id == user_id)
                # Update existing user info
                if provider == 'google':
                    user.name = user_info['name']
                    user.avatar_url = user_info.get('picture')
                elif provider == 'github':
                    user.name = user_info.get('name') or user_info.get('login')
                    user.avatar_url = user_info.get('avatar_url')
                elif provider == 'reddit':
                    user.name = user_info['name']
                    user.avatar_url = user_info.get('icon_img', '').split('?')[0] if user_info.get('icon_img') else None
                user.last_login = datetime.now()
                user.save()
            except User.DoesNotExist:
                # Create new user
                if provider == 'google':
                    user = User.create(
                        id=user_id,
                        email=user_info['email'],
                        name=user_info['name'],
                        avatar_url=user_info.get('picture'),
                        provider='google',
                        last_login=datetime.now()
                    )
                elif provider == 'github':
                    user = User.create(
                        id=user_id,
                        email=primary_email,
                        name=user_info.get('name') or user_info.get('login'),
                        avatar_url=user_info.get('avatar_url'),
                        provider='github',
                        last_login=datetime.now()
                    )
                elif provider == 'reddit':
                    user = User.create(
                        id=user_id,
                        email=constructed_email,
                        name=user_info['name'],
                        avatar_url=user_info.get('icon_img', '').split('?')[0] if user_info.get('icon_img') else None,
                        provider='reddit',
                        last_login=datetime.now()
                    )
            
            login_user(user, remember=True)
            flash(f'Successfully logged in with {provider.title()}!', 'success')
        except Exception as db_error:
            print(f"Database error: {db_error}")
            flash(f'Database error during login: {str(db_error)}', 'error')
            return redirect(url_for('auth.login'))
        
        # Redirect to next page or appropriate landing page
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        
        # For new users without applications, redirect to profile to see "Join Community"
        user_role = getattr(user, 'role', None)
        if user_role not in ['approved', 'pending', 'organizer', 'admin']:
            return redirect(url_for('auth.profile'))
        
        # For existing users, redirect to home
        return redirect(url_for('pages.index'))
        
    except Exception as e:
        print(f"OAuth error for {provider}: {str(e)}")
        flash(f'Authentication failed: {str(e)}', 'error')
        return redirect(url_for('auth.login'))


@bp.route('/logout')
@login_required
def logout():
    """Log out current user"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('pages.index'))


@bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    # Show welcome message for new users
    user_role = getattr(current_user, 'role', None)
    if user_role not in ['approved', 'pending', 'organizer', 'admin']:
        flash('Welcome! Ready to join our community? Complete the application below to get started.', 'info')
    
    return render_template('user/profile.html', user=current_user)
