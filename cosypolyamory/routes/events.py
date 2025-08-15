"""
Event routes for cosypolyamory.org

Handles event listing, creation, editing, and RSVP management.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

bp = Blueprint('events', __name__, url_prefix='/events')

# Event route implementations will be moved here from app.py
# during the refactoring process
