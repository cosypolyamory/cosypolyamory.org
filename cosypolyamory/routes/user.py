"""
User routes for cosypolyamory.org

Handles user applications, profile management, and related functionality.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

bp = Blueprint('user', __name__)

# User route implementations will be moved here from app.py
# during the refactoring process
