"""
Authentication routes for cosypolyamory.org

Handles OAuth login, logout, and profile management.
"""

import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user

from cosypolyamory.models.user import User
from cosypolyamory.database import database

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
        return oauth.google.authorize_redirect(redirect_uri)
    elif provider == 'github':
        redirect_uri = url_for('auth.oauth_callback', provider='github', _external=True)
        return oauth.github.authorize_redirect(redirect_uri)
    elif provider == 'reddit':
        redirect_uri = url_for('auth.oauth_callback', provider='reddit', _external=True)
        # Reddit requires a unique state parameter for security
        return oauth.reddit.authorize_redirect(redirect_uri, duration='permanent')
    elif provider == 'musicbrainz':
        redirect_uri = url_for('auth.oauth_callback', provider='musicbrainz', _external=True)
        return oauth.musicbrainz.authorize_redirect(redirect_uri)
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
            # Get user info from Google API
            resp = oauth.google.get('userinfo', token=token)
            user_info = resp.json()
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
            resp = oauth.github.get('user', token=token)
            user_info = resp.json()
            
            # Check if user_info is valid
            if not isinstance(user_info, dict) or 'id' not in user_info:
                raise Exception(f"Invalid user info received from GitHub: {user_info}")
            
            # Get user email (may require additional API call)
            primary_email = user_info.get('email')  # Try to get email from user info first
            if not primary_email:
                try:
                    email_resp = oauth.github.get('user/emails', token=token)
                    emails = email_resp.json()
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
            
            # Get user info from Reddit API
            resp = oauth.reddit.get('api/v1/me', token=token)
            user_info = resp.json()
            
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
        elif provider == 'musicbrainz':
            token = oauth.musicbrainz.authorize_access_token()
            
            # MusicBrainz OAuth is primarily for accessing private data, not user identification
            username = None
            
            # Check if token is valid
            if not token:
                raise Exception("No token received from MusicBrainz")
            
            print(f"MusicBrainz token details: {token}")
            
            # Try to get username from MusicBrainz Web Service API
            if not username:
                try:
                    # Try collections endpoint which might reveal the user
                    resp = oauth.musicbrainz.get('ws/2/collection', token=token, params={
                        'fmt': 'json'
                    }, headers={
                        'User-Agent': 'CozyPolyamory/1.0 (https://cosypolyamory.org)',
                        'Accept': 'application/json'
                    })
                    
                    print(f"MusicBrainz collections response status: {resp.status_code}")
                    print(f"MusicBrainz collections response: {resp.text[:200]}...")
                    
                    if resp.status_code == 200 and resp.text.strip():
                        try:
                            collections_data = resp.json()
                            print(f"MusicBrainz collections data: {collections_data}")
                            
                            # Try to extract username from collections data
                            if isinstance(collections_data, dict) and 'collections' in collections_data:
                                if len(collections_data['collections']) > 0:
                                    first_collection = collections_data['collections'][0]
                                    if 'editor' in first_collection:
                                        username = first_collection['editor']
                                    elif 'owner' in first_collection:
                                        username = first_collection['owner']
                        except Exception as parse_error:
                            print(f"Error parsing collections response: {parse_error}")
                except Exception as e:
                    print(f"MusicBrainz collections API error: {e}")
            
            # If still no username, try to decode the access token manually
            if not username:
                try:
                    import base64
                    import json
                    
                    access_token = token.get('access_token', '')
                    if '.' in access_token:  # Looks like a JWT
                        print(f"Attempting to decode JWT token...")
                        
                        # Split the JWT token
                        parts = access_token.split('.')
                        if len(parts) >= 2:
                            payload = parts[1]
                            # Add padding if needed for base64 decoding
                            payload += '=' * (4 - len(payload) % 4)
                            
                            try:
                                decoded_bytes = base64.urlsafe_b64decode(payload)
                                decoded_str = decoded_bytes.decode('utf-8')
                                payload_data = json.loads(decoded_str)
                                print(f"JWT payload: {payload_data}")
                                
                                # Look for username in various JWT claim fields
                                username = (payload_data.get('sub') or 
                                          payload_data.get('username') or 
                                          payload_data.get('user_name') or
                                          payload_data.get('preferred_username') or
                                          payload_data.get('name'))
                                
                                if username:
                                    print(f"Found username in JWT: {username}")
                            except Exception as decode_error:
                                print(f"JWT decode error: {decode_error}")
                except Exception as token_error:
                    print(f"Token parsing error: {token_error}")
            
            # Generate a user-friendly temporary username if we couldn't get the real one
            if not username:
                import hashlib
                # Use a more stable hash based on the token to ensure consistency
                token_str = str(token.get('access_token', token))
                token_hash = hashlib.md5(token_str.encode()).hexdigest()[:8]
                username = f"mb_user_{token_hash}"
                print(f"Generated temporary MusicBrainz username: {username}")
                print("Note: MusicBrainz OAuth doesn't provide usernames. User can update profile later.")
            else:
                print(f"Successfully extracted MusicBrainz username: {username}")
            
            user_id = f"musicbrainz_{username}"
            constructed_email = f"{username}@musicbrainz.local"
            
            user = User(
                user_id=user_id,
                email=constructed_email,
                name=username,
                avatar_url=None,  # MusicBrainz doesn't provide avatars
                provider='musicbrainz'
            )
        else:
            flash('Unknown OAuth provider', 'error')
            return redirect(url_for('auth.login'))
        
        # Store user in database and login
        try:
            with database.atomic():
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
                    elif provider == 'musicbrainz':
                        user.name = username
                        user.avatar_url = None  # MusicBrainz doesn't provide avatars
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
                    elif provider == 'musicbrainz':
                        user = User.create(
                            id=user_id,
                            email=constructed_email,
                            name=username,
                            avatar_url=None,  # MusicBrainz doesn't provide avatars
                            provider='musicbrainz',
                            last_login=datetime.now()
                        )
            
            login_user(user, remember=True)
            flash(f'Successfully logged in with {provider.title()}!', 'success')
        except Exception as db_error:
            print(f"Database error: {db_error}")
            error_msg = str(db_error)
            
            # Check for specific constraint failures and provide user-friendly messages
            if 'NOT NULL constraint failed: users.email' in error_msg or ('UNIQUE constraint failed' in error_msg and 'email' in error_msg):
                flash('This email address is already associated with another account. Please use a different login method or account.', 'error')
            else:
                flash(f'Database error during login: {error_msg}', 'error')
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
    
    # Check if user needs to provide email/name (for Reddit/MusicBrainz users)
    needs_info = False
    if current_user.provider in ['reddit', 'musicbrainz']:
        if (current_user.email.endswith('@reddit.local') or 
            current_user.email.endswith('@musicbrainz.local') or
            current_user.name.startswith('mb_user_') or
            current_user.name.startswith('musicbrainz_user_')):
            needs_info = True
    
    # Get stored form data from session (for retaining values after errors)
    form_data = session.get('profile_form_data', {})
    show_edit_modal = bool(form_data)  # Show edit modal if there's stored form data
    
    # Clear form data from session after we've retrieved it
    if form_data:
        session.pop('profile_form_data', None)
    
    return render_template('user/profile.html', 
                         user=current_user, 
                         needs_info=needs_info,
                         form_data=form_data,
                         show_edit_modal=show_edit_modal)


@bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile information"""
    email = request.form.get('email', '').strip()
    name = request.form.get('name', '').strip()
    pronoun_singular = request.form.get('pronoun_singular', '').strip()
    pronoun_plural = request.form.get('pronoun_plural', '').strip()
    
    # Check if this is an AJAX request by looking at Accept header or explicit parameter
    is_ajax = ('application/json' in request.headers.get('Accept', '')) or \
              request.args.get('format') == 'json' or \
              request.form.get('ajax') == '1'
    
    # For non-AJAX requests, store form data in session in case we need to redirect back
    if not is_ajax:
        session['profile_form_data'] = {
            'email': email,
            'name': name,
            'pronoun_singular': pronoun_singular,
            'pronoun_plural': pronoun_plural
        }
    
    # Validation
    if not email or not name:
        error_msg = 'Both email and name are required.'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        flash(error_msg, 'error')
        return redirect(url_for('auth.profile'))
    
    # Basic email validation
    if '@' not in email or '.' not in email:
        error_msg = 'Please enter a valid email address.'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        flash(error_msg, 'error')
        return redirect(url_for('auth.profile'))
    
    # Check if email is already taken by another user
    try:
        existing_user = User.get(User.email == email)
        if existing_user.id != current_user.id:
            error_msg = 'This email address is already in use by another account.'
            if is_ajax:
                return jsonify({'success': False, 'error': error_msg})
            flash(error_msg, 'error')
            return redirect(url_for('auth.profile'))
    except User.DoesNotExist:
        pass  # Email is available
    
    try:
        with database.atomic():
            # Update user information
            current_user.email = email
            current_user.name = name
            current_user.pronoun_singular = pronoun_singular if pronoun_singular else None
            current_user.pronoun_plural = pronoun_plural if pronoun_plural else None
            current_user.save()
            
            # Refresh the current user session to ensure updated data is reflected
            # This is important because Flask-Login caches the user object
            from flask_login import login_user
            login_user(current_user, remember=True)
        
        # Clear form data from session on successful update
        if not is_ajax:
            session.pop('profile_form_data', None)
        
        success_msg = 'Profile updated successfully!'
        if is_ajax:
            return jsonify({'success': True, 'message': success_msg})
        flash(success_msg, 'success')
    except Exception as e:
        error_msg = f'Error updating profile: {str(e)}'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        flash(error_msg, 'error')
    
    return redirect(url_for('auth.profile'))
