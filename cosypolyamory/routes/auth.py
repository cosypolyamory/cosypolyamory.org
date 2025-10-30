"""
Authentication routes for cosypolyamory.org

Handles OAuth login, logout, and profile management.
"""

import os
import re
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user

from cosypolyamory.models.user import User
from cosypolyamory.models.rsvp import RSVP
from cosypolyamory.models.event import Event
from cosypolyamory.database import database

bp = Blueprint('auth', __name__)

# Note: OAuth clients (google, github, reddit) need to be imported in app.py


@bp.route('/login')
def login():
    """Display login page with OAuth providers"""
    return render_template('user/login.html')


@bp.route('/join')
def join():
    """Display join community page"""
    return render_template('user/join.html')


@bp.route('/create-account')
def create_account():
    """Display create account page with OAuth providers"""
    return render_template('user/login.html', page_title='Create an account', is_signup=True)


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
                # Try to get a stable user identifier from MusicBrainz
                user_id_from_mb = None
                
                # Try to get user profile/whoami to get a stable user ID
                try:
                    resp = oauth.musicbrainz.get('oauth2/userinfo', token=token, headers={
                        'User-Agent': 'CozyPolyamory/1.0 (https://cosypolyamory.org)',
                        'Accept': 'application/json'
                    })
                    
                    if resp.status_code == 200:
                        user_data = resp.json()
                        print(f"MusicBrainz userinfo response: {user_data}")
                        user_id_from_mb = user_data.get('sub') or user_data.get('id') or user_data.get('user_id')
                        if user_id_from_mb:
                            username = f"mb_{user_id_from_mb}"
                            print(f"Found stable MusicBrainz user ID: {user_id_from_mb}")
                except Exception as e:
                    print(f"Error getting MusicBrainz userinfo: {e}")
                
                # If we still don't have a stable ID, check if we can get it from the token payload
                if not username and token.get('access_token'):
                    try:
                        import base64
                        import json
                        
                        access_token = token.get('access_token', '')
                        if '.' in access_token:  # JWT token
                            parts = access_token.split('.')
                            if len(parts) >= 2:
                                payload = parts[1]
                                payload += '=' * (4 - len(payload) % 4)
                                
                                try:
                                    decoded_bytes = base64.urlsafe_b64decode(payload)
                                    decoded_str = decoded_bytes.decode('utf-8')
                                    payload_data = json.loads(decoded_str)
                                    
                                    # Look for a stable user ID in the JWT
                                    stable_id = (payload_data.get('sub') or 
                                               payload_data.get('user_id') or
                                               payload_data.get('id'))
                                    
                                    if stable_id:
                                        username = f"mb_{stable_id}"
                                        print(f"Found stable MusicBrainz ID in JWT: {stable_id}")
                                except Exception as decode_error:
                                    print(f"JWT decode error: {decode_error}")
                    except Exception as token_error:
                        print(f"Token parsing error: {token_error}")
                
                # Last resort: use a hash of the refresh token or other stable data
                if not username:
                    import hashlib
                    # Use refresh token if available (more stable than access token)
                    stable_data = token.get('refresh_token') or token.get('access_token', str(token))
                    token_hash = hashlib.md5(stable_data.encode()).hexdigest()[:12]  # Longer hash for uniqueness
                    username = f"mb_user_{token_hash}"
                    print(f"Generated fallback MusicBrainz username: {username}")
                    print("Warning: Could not get stable MusicBrainz user ID. Using fallback identifier.")
                    
                print("Note: MusicBrainz OAuth has limited user identification. User can update profile later.")
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
                user_found = False
                try:
                    user = User.get(User.id == user_id)
                    user_found = True
                except User.DoesNotExist:
                    # For MusicBrainz, also try to find by email in case the user_id changed
                    # due to improved identification methods
                    if provider == 'musicbrainz':
                        try:
                            # Look for existing MusicBrainz user with the same email
                            existing_user = User.get(
                                (User.email == constructed_email) & 
                                (User.provider == 'musicbrainz')
                            )
                            # If we found a user with the same email but different ID,
                            # this might be the same user with an improved identifier
                            print(f"Found existing MusicBrainz user with same email: {existing_user.id}")
                            print(f"New identifier would be: {user_id}")
                            
                            # Update the user's ID to the new, more stable identifier
                            # But first check if the new ID is actually different and more stable
                            old_id = existing_user.id
                            if (old_id.startswith('musicbrainz_mb_user_') and 
                                (user_id.startswith('musicbrainz_mb_') and not user_id.startswith('musicbrainz_mb_user_'))):
                                print(f"Upgrading MusicBrainz user ID from {old_id} to {user_id}")
                                # Create new user record with the better ID
                                existing_user.id = user_id
                                existing_user.save()
                                user = existing_user
                                user_found = True
                            else:
                                user = existing_user
                                user_found = True
                        except User.DoesNotExist:
                            pass  # Will create new user below
                
                if user_found:
                    # Update existing user info, but preserve custom names
                    if provider == 'google':
                        oauth_name = user_info['name']
                        # Only update name if user hasn't customized it or if it still matches the OAuth default
                        if user.name == f"google_user_{user_id.split('_')[1]}" or user.name == oauth_name:
                            user.name = oauth_name
                        user.avatar_url = user_info.get('picture')
                    elif provider == 'github':
                        oauth_name = user_info.get('name') or user_info.get('login')
                        # Only update name if user hasn't customized it or if it still matches the OAuth default
                        if user.name == user_info.get('login') or user.name == oauth_name:
                            user.name = oauth_name
                        user.avatar_url = user_info.get('avatar_url')
                    elif provider == 'reddit':
                        oauth_name = user_info['name']
                        # Only update name if user hasn't customized it or if it still matches the OAuth default
                        if user.name == oauth_name:
                            user.name = oauth_name
                        user.avatar_url = user_info.get('icon_img', '').split('?')[0] if user_info.get('icon_img') else None
                    elif provider == 'musicbrainz':
                        # For MusicBrainz, only update name if it's still the auto-generated username
                        # Don't overwrite if user has customized their display name
                        if user.name.startswith('mb_user_') or user.name.startswith('musicbrainz_user_') or user.name == username:
                            user.name = username
                        user.avatar_url = None  # MusicBrainz doesn't provide avatars
                    user.last_login = datetime.now()
                    user.save()
                else:
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
        
        return redirect(url_for('auth.profile'))
        
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
    
    # Check if user needs to provide required profile information
    needs_info = False
    
    # Check for missing or placeholder email
    if (not current_user.email or 
        current_user.email.endswith('@reddit.local') or 
        current_user.email.endswith('@musicbrainz.local')):
        needs_info = True
    
    # Check for missing or placeholder name
    if (not current_user.name or 
        current_user.name.startswith('mb_user_') or
        current_user.name.startswith('musicbrainz_user_')):
        needs_info = True
    
    # Check for missing pronouns
    if not current_user.pronouns:
        needs_info = True
    
    # Get stored form data from session (for retaining values after errors)
    form_data = session.get('profile_form_data', {})
    show_edit_modal = bool(form_data)  # Show edit modal if there's stored form data
    
    # Clear form data from session after we've retrieved it
    if form_data:
        session.pop('profile_form_data', None)
    
    # Get user's RSVPs for approved users (upcoming events only)
    user_rsvps = []
    if current_user.role not in ("new", "pending"):
        try:
            user_rsvps = (RSVP
                         .select(RSVP, Event)
                         .join(Event)
                         .where(
                             (RSVP.user == current_user) &
                             (Event.exact_time >= datetime.now())  # Only upcoming events
                         )
                         .order_by(Event.exact_time.asc())  # Order by upcoming date ascending
                         .limit(10))  # Show next 10 upcoming RSVPs
        except Exception as e:
            print(f"Error fetching user RSVPs: {e}")
            user_rsvps = []
    
    return render_template('user/profile.html', 
                         user=current_user, 
                         needs_info=needs_info,
                         form_data=form_data,
                         show_edit_modal=show_edit_modal,
                         user_rsvps=user_rsvps,
                         now=datetime.now())


@bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile information"""
    email = request.form.get('email', '').strip()
    name = request.form.get('name', '').strip()
    pronouns = request.form.get('pronoun_singular', '').strip()  # Keep old field name for backwards compatibility
    
    # Check if this is an AJAX request by looking at Accept header or explicit parameter
    is_ajax = ('application/json' in request.headers.get('Accept', '')) or \
              request.args.get('format') == 'json' or \
              request.form.get('ajax') == '1'
    
    # For non-AJAX requests, store form data in session in case we need to redirect back
    if not is_ajax:
        session['profile_form_data'] = {
            'email': email,
            'name': name,
            'pronoun_singular': pronouns,  # Keep old field name for template compatibility
        }
    
    # Validation
    if not email or not name:
        error_msg = 'Both email and name are required.'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        flash(error_msg, 'error')
        return redirect(url_for('auth.profile'))
    
    # Validate pronouns are provided
    if not pronouns:
        error_msg = 'Pronouns are required.'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        flash(error_msg, 'error')
        return redirect(url_for('auth.profile'))
    
    # Validate pronouns format: 2-15 alphanumeric characters, slash, 2-15 alphanumeric characters
    pronoun_pattern = r'^[a-zA-Z0-9]{2,15}/[a-zA-Z0-9]{2,15}$'
    if not re.match(pronoun_pattern, pronouns):
        error_msg = 'Pronouns must be in format: word/word (e.g., they/them, she/her, he/him). Each part should be 2-15 alphanumeric characters.'
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
            current_user.pronouns = pronouns
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
