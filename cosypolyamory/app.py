#!/usr/bin/env python3

import os
import json
import sys
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, send_file, session, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

# Import database and models
from cosypolyamory.database import init_database
from cosypolyamory.models.user import User
from cosypolyamory.models.user_application import UserApplication
from cosypolyamory.models.event import Event
from cosypolyamory.models.rsvp import RSVP

# Load environment variables
load_dotenv()

STATIC_PATH = "/static"
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static')
TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), 'templates')

app = Flask(__name__,
            static_url_path = STATIC_PATH,
            static_folder = STATIC_FOLDER,
            template_folder = TEMPLATE_FOLDER)

# Configure Flask app
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize database
init_database()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Initialize OAuth
oauth = OAuth(app)

# Configure OAuth providers
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v2/',
    client_kwargs={'scope': 'openid email profile'},
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
)

github = oauth.register(
    name='github',
    client_id=os.getenv('GITHUB_CLIENT_ID'),
    client_secret=os.getenv('GITHUB_CLIENT_SECRET'),
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

# In-memory user storage replaced with database
# users = {} - removed

@login_manager.user_loader
def load_user(user_id):
    """Load user from database"""
    try:
        return User.get(User.id == user_id)
    except User.DoesNotExist:
        return None

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        # Check if user has admin status in database
        if not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def organizer_required(f):
    """Decorator to require organizer access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.can_organize_events():
            flash('Organizer access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_or_organizer_required(f):
    """Decorator to require admin or organizer access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not (current_user.is_admin or current_user.is_organizer):
            flash('Admin or Organizer access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def approved_user_required(f):
    """Decorator to require approved user status"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.is_approved and not current_user.is_organizer and not current_user.is_admin:
            flash('Community approval required to access this feature.', 'info')
            return redirect(url_for('application_status'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/robots.txt')
def robots_txt():
    return send_file("static/robots.txt")

@app.route('/sitemap.xml')
def sitemap_xml():
    return send_file("static/sitemap.xml")

@app.route('/')
def index():
    return render_template("index.html", page="home")

@app.route('/contact')
def contact():
    return render_template("contact.html", page="contact")

@app.route('/values')
def values():
    return render_template("values.html", page="values")

@app.route('/structure')
def rules():
    return render_template("structure.html", page="docs")

@app.route('/governance')
def governance():
    return render_template("governance.html", page="docs")

@app.route('/conflict-resolution')
def conflict():
    return send_file("static/pdf/Cosy Polyamory Community - Conflict Resolution Protocol.pdf")

@app.route('/code-of-conduct')
def coc():
    return render_template("code-of-conduct.html", page="docs")

@app.route('/events-guide')
def eventsGuide():
    return render_template("events-guide.html", page="docs")

# OAuth Routes
@app.route('/login')
def login():
    """Display login page with OAuth providers"""
    return render_template('login.html')

@app.route('/login/<provider>')
def oauth_login(provider):
    """Initiate OAuth login with specified provider"""
    print(f"Attempting to login with {provider}")
    if provider == 'google':
        redirect_uri = url_for('oauth_callback', provider='google', _external=True)
        print(f"Google redirect URI: {redirect_uri}")
        return google.authorize_redirect(redirect_uri)
    elif provider == 'github':
        redirect_uri = url_for('oauth_callback', provider='github', _external=True)
        print(f"GitHub redirect URI: {redirect_uri}")
        print(f"GitHub client ID: {os.getenv('GITHUB_CLIENT_ID')}")
        return github.authorize_redirect(redirect_uri)
    else:
        flash('Unknown OAuth provider', 'error')
        return redirect(url_for('login'))

@app.route('/callback/<provider>')
def oauth_callback(provider):
    """Handle OAuth callback and create user session"""
    try:
        print(f"Processing callback for {provider}")
        if provider == 'google':
            token = google.authorize_access_token()
            print(f"Google token received: {type(token)}")
            # Get user info from Google API
            resp = google.get('userinfo', token=token)
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
            token = github.authorize_access_token()
            print(f"GitHub token received: {type(token)}")
            resp = github.get('user', token=token)
            user_info = resp.json()
            print(f"GitHub user_info: {user_info}")
            
            # Check if user_info is valid
            if not isinstance(user_info, dict) or 'id' not in user_info:
                raise Exception(f"Invalid user info received from GitHub: {user_info}")
            
            # Get user email (may require additional API call)
            primary_email = user_info.get('email')  # Try to get email from user info first
            if not primary_email:
                try:
                    email_resp = github.get('user/emails', token=token)
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
        else:
            flash('Unknown OAuth provider', 'error')
            return redirect(url_for('login'))
        
        # Store user in database and login
        try:
            # Try to get existing user or create new one
            try:
                user = User.get(User.id == user_id)
                # Update existing user info
                user.name = user.name if provider == 'google' else (user_info.get('name') or user_info.get('login'))
                user.avatar_url = user.avatar_url if provider == 'google' else user_info.get('avatar_url')
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
                else:  # github
                    user = User.create(
                        id=user_id,
                        email=primary_email,
                        name=user_info.get('name') or user_info.get('login'),
                        avatar_url=user_info.get('avatar_url'),
                        provider='github',
                        last_login=datetime.now()
                    )
            
            login_user(user, remember=True)
            flash(f'Successfully logged in with {provider.title()}!', 'success')
        except Exception as db_error:
            print(f"Database error: {db_error}")
            flash(f'Database error during login: {str(db_error)}', 'error')
            return redirect(url_for('login'))
        
        # Redirect to next page or appropriate landing page
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        
        # For new users without applications, redirect to profile to see "Join Community"
        user_role = getattr(user, 'role', None)
        if user_role not in ['approved', 'pending', 'organizer', 'admin']:
            return redirect(url_for('profile'))
        
        # For existing users, redirect to home
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"OAuth error for {provider}: {str(e)}")
        flash(f'Authentication failed: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    """Log out current user"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    # Show welcome message for new users
    user_role = getattr(current_user, 'role', None)
    if user_role not in ['approved', 'pending', 'organizer', 'admin']:
        flash('Welcome! Ready to join our community? Complete the application below to get started.', 'info')
    
    return render_template('profile.html', user=current_user)

# API Routes for AJAX requests
@app.route('/api/user')
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

@app.route('/api/admin/change-role', methods=['POST'])
@admin_required
def api_change_user_role():
    """Change a user's role (admin only)"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_role = data.get('role')
        
        if not user_id or not new_role:
            return jsonify({'success': False, 'error': 'Missing user_id or role'})
        
        if new_role not in ['admin', 'organizer', 'approved', 'pending', 'rejected']:
            return jsonify({'success': False, 'error': 'Invalid role'})
        
        # Check if trying to make admin and current user is not admin
        if new_role == 'admin' and not current_user.is_admin:
            return jsonify({'success': False, 'error': 'Only admins can make other users admin'})
        
        # Find the user
        try:
            user = User.get(User.id == user_id)
        except User.DoesNotExist:
            return jsonify({'success': False, 'error': 'User not found'})
        
        # Update user role and corresponding boolean flags
        user.role = new_role
        user.is_admin = (new_role == 'admin')
        user.is_organizer = (new_role == 'organizer')
        user.is_approved = (new_role in ['admin', 'organizer', 'approved'])
        
        user.save()
        
        return jsonify({
            'success': True, 
            'message': f'User role changed to {new_role}',
            'user_id': user_id,
            'new_role': new_role
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/delete-user', methods=['DELETE'])
@admin_required
def api_delete_user():
    """Delete a user (admin only)"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Missing user_id'})
        
        # Find the user
        try:
            user = User.get(User.id == user_id)
        except User.DoesNotExist:
            return jsonify({'success': False, 'error': 'User not found'})
        
        # Prevent self-deletion
        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot delete your own account'})
        
        # Delete related records first (UserApplication, RSVP, etc.)
        from cosypolyamory.models.user_application import UserApplication
        from cosypolyamory.models.rsvp import RSVP
        
        # Delete user applications
        UserApplication.delete().where(UserApplication.user == user).execute()
        
        # Delete RSVPs
        RSVP.delete().where(RSVP.user == user).execute()
        
        # Delete the user
        user_name = user.name
        user.delete_instance()
        
        return jsonify({
            'success': True, 
            'message': f'User {user_name} deleted successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Application System Routes
@app.route('/apply')
@login_required
def apply():
    """Community application form"""
    # Check if user already has an application
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        return redirect(url_for('application_status'))
    except UserApplication.DoesNotExist:
        pass
    
    # Get questions from environment
    questions = {
        'question_1': os.getenv('APPLICATION_QUESTION_1', 'Question 1'),
        'question_2': os.getenv('APPLICATION_QUESTION_2', 'Question 2'),
        'question_3': os.getenv('APPLICATION_QUESTION_3', 'Question 3'),
        'question_4': os.getenv('APPLICATION_QUESTION_4', 'Question 4'),
        'question_5': os.getenv('APPLICATION_QUESTION_5', 'Question 5'),
    }
    
    return render_template('apply.html', questions=questions)

@app.route('/apply', methods=['POST'])
@login_required
def submit_application():
    """Submit community application"""
    # Check if user already has an application
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        flash('You have already submitted an application.', 'info')
        return redirect(url_for('application_status'))
    except UserApplication.DoesNotExist:
        pass
    
    # Create application
    application = UserApplication.create(
        user=current_user,
        question_1_answer=request.form.get('question_1', ''),
        question_2_answer=request.form.get('question_2', ''),
        question_3_answer=request.form.get('question_3', ''),
        question_4_answer=request.form.get('question_4', ''),
        question_5_answer=request.form.get('question_5', ''),
    )
    
    flash('Your application has been submitted! You will be notified once it has been reviewed.', 'success')
    return redirect(url_for('application_status'))

@app.route('/application-status')
@login_required
def application_status():
    """Show user's application status"""
    try:
        application = UserApplication.get(UserApplication.user == current_user)
        return render_template('application_status.html', application=application)
    except UserApplication.DoesNotExist:
        return redirect(url_for('apply'))

# Moderation Routes
@app.route('/moderate')
@organizer_required
def moderate_applications():
    """Application moderation queue"""
    pending_applications = UserApplication.select().where(UserApplication.status == 'pending').order_by(UserApplication.submitted_at)
    return render_template('moderate.html', applications=pending_applications)

@app.route('/moderate/<int:application_id>/approve', methods=['POST'])
@organizer_required
def approve_application(application_id):
    """Approve a user application"""
    try:
        application = UserApplication.get_by_id(application_id)
        application.status = 'approved'
        application.reviewed_at = datetime.now()
        application.reviewed_by = current_user
        application.review_notes = request.form.get('notes', '')
        application.save()
        
        # Update user status
        user = application.user
        user.is_approved = True
        user.save()
        
        flash(f'Application for {user.name} has been approved.', 'success')
    except UserApplication.DoesNotExist:
        flash('Application not found.', 'error')
    
    return redirect(url_for('moderate_applications'))

@app.route('/moderate/<int:application_id>/reject', methods=['POST'])
@organizer_required
def reject_application(application_id):
    """Reject a user application"""
    try:
        application = UserApplication.get_by_id(application_id)
        application.status = 'rejected'
        application.reviewed_at = datetime.now()
        application.reviewed_by = current_user
        application.review_notes = request.form.get('notes', '')
        application.save()
        
        flash(f'Application for {application.user.name} has been rejected.', 'info')
    except UserApplication.DoesNotExist:
        flash('Application not found.', 'error')
    
    return redirect(url_for('moderate_applications'))

# Events System Routes
@app.route('/events')
@login_required
def events_list():
    """List all events with appropriate visibility"""
    events = Event.select().where(Event.is_active == True).order_by(Event.date)
    can_see_details = current_user.can_see_full_event_details()
    return render_template('events_list.html', events=events, can_see_details=can_see_details)

@app.route('/events/<int:event_id>')
@login_required
def event_detail(event_id):
    """Show event details"""
    try:
        event = Event.get_by_id(event_id)
        can_see_details = current_user.can_see_full_event_details()
        
        # Get user's RSVP if exists
        user_rsvp = None
        try:
            user_rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == current_user))
        except RSVP.DoesNotExist:
            pass
        
        # Get RSVP counts
        rsvp_counts = {
            'yes': RSVP.select().where((RSVP.event == event) & (RSVP.status == 'yes')).count(),
            'maybe': RSVP.select().where((RSVP.event == event) & (RSVP.status == 'maybe')).count(),
            'no': RSVP.select().where((RSVP.event == event) & (RSVP.status == 'no')).count()
        }
        
        return render_template('event_detail.html', 
                             event=event, 
                             can_see_details=can_see_details,
                             user_rsvp=user_rsvp,
                             rsvp_counts=rsvp_counts)
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events_list'))

@app.route('/events/create')
@organizer_required
def create_event():
    """Create new event form"""
    return render_template('create_event.html')

@app.route('/events/create', methods=['POST'])
@organizer_required
def create_event_post():
    """Create new event"""
    from datetime import datetime as dt
    
    try:
        # Parse the form data
        title = request.form.get('title')
        description = request.form.get('description')
        barrio = request.form.get('barrio')
        time_period = request.form.get('time_period')
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        establishment_name = request.form.get('establishment_name')
        google_maps_link = request.form.get('google_maps_link')
        location_notes = request.form.get('location_notes')
        tips_for_attendees = request.form.get('tips_for_attendees')
        max_attendees = request.form.get('max_attendees')
        co_host_id = request.form.get('co_host_id', '')
        
        # Parse dates and times
        date = dt.strptime(date_str, '%Y-%m-%d')
        exact_time = dt.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
        
        # Validate Google Maps link
        if not google_maps_link or 'maps.google' not in google_maps_link.lower():
            flash('Please provide a valid Google Maps link.', 'error')
            return redirect(url_for('create_event'))
        
        # Handle co-host
        co_host = None
        if co_host_id:
            try:
                co_host = User.get_by_id(co_host_id)
                if not co_host.can_organize_events():
                    flash('Co-host must be an organizer.', 'error')
                    return redirect(url_for('create_event'))
            except User.DoesNotExist:
                flash('Co-host not found.', 'error')
                return redirect(url_for('create_event'))
        
        # Create event
        event = Event.create(
            title=title,
            description=description,
            barrio=barrio,
            time_period=time_period,
            date=date,
            establishment_name=establishment_name,
            google_maps_link=google_maps_link,
            location_notes=location_notes or None,
            exact_time=exact_time,
            organizer=current_user,
            co_host=co_host,
            tips_for_attendees=tips_for_attendees or None,
            max_attendees=int(max_attendees) if max_attendees else None
        )
        
        flash(f'Event "{title}" has been created successfully!', 'success')
        return redirect(url_for('event_detail', event_id=event.id))
        
    except ValueError as e:
        flash(f'Error creating event: {str(e)}', 'error')
        return redirect(url_for('create_event'))
    except Exception as e:
        flash(f'Unexpected error: {str(e)}', 'error')
        return redirect(url_for('create_event'))

@app.route('/events/<int:event_id>/rsvp', methods=['POST'])
@approved_user_required
def rsvp_event(event_id):
    """RSVP to an event"""
    try:
        event = Event.get_by_id(event_id)
        status = request.form.get('status')
        notes = request.form.get('notes', '')
        
        if status not in ['yes', 'no', 'maybe']:
            flash('Invalid RSVP status.', 'error')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # Update or create RSVP
        try:
            rsvp = RSVP.get((RSVP.event == event) & (RSVP.user == current_user))
            rsvp.status = status
            rsvp.notes = notes
            rsvp.updated_at = datetime.now()
            rsvp.save()
            flash(f'RSVP updated to "{status.title()}"', 'success')
        except RSVP.DoesNotExist:
            RSVP.create(
                event=event,
                user=current_user,
                status=status,
                notes=notes
            )
            flash(f'RSVP set to "{status.title()}"', 'success')
        
        return redirect(url_for('event_detail', event_id=event_id))
        
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('events_list'))

@app.route('/admin')
@admin_or_organizer_required
def admin():
    """Admin dashboard"""
    users = list(User.select())
    return render_template('admin.html', users=users)

