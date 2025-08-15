"""
API Blueprint Registry

This module creates and configures the main API blueprint and registers all API sub-modules.
All API endpoints are prefixed with /api/
"""

from flask import Blueprint
from . import users, admin, applications

# Main API blueprint
bp = Blueprint('api', __name__, url_prefix='/api')

# Register sub-blueprints
bp.register_blueprint(users.bp)
bp.register_blueprint(admin.bp)  
bp.register_blueprint(applications.bp)
