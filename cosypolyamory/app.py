#!/usr/bin/env python3

import os
import json
import sys
import re
import urllib.parse
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, send_file, session, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask_assets import Environment, Bundle

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
login_manager.login_view = 'auth.login'
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

reddit = oauth.register(
    name='reddit',
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    access_token_url='https://www.reddit.com/api/v1/access_token',
    authorize_url='https://www.reddit.com/api/v1/authorize',
    api_base_url='https://oauth.reddit.com/',
    client_kwargs={'scope': 'identity'},
    token_endpoint_auth_method='client_secret_basic',  # Reddit requires basic auth
)

musicbrainz = oauth.register(
    name='musicbrainz',
    client_id=os.getenv('MUSICBRAINZ_CLIENT_ID'),
    client_secret=os.getenv('MUSICBRAINZ_CLIENT_SECRET'),
    access_token_url='https://musicbrainz.org/oauth2/token',
    authorize_url='https://musicbrainz.org/oauth2/authorize',
    api_base_url='https://musicbrainz.org/',
    client_kwargs={'scope': 'profile email'},
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

# Initialize Flask-Assets
assets = Environment(app)
scss = Bundle(
    'scss/style.scss',
    filters='libsass',
    output='css/style.css'
)
assets.register('scss_all', scss)

# Register route blueprints
from cosypolyamory.routes import register_routes
register_routes(app)

