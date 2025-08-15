"""
Route modules for the cosypolyamory Flask application.

This package contains the view functions organized by functional area:
- pages: Static content pages
- auth: Authentication and OAuth
- user: User profiles and applications  
- events: Event management
- admin: Administrative interface
- api: API endpoints
"""

from flask import Blueprint

def register_routes(app):
    """Register all route blueprints with the Flask app"""
    from . import pages, auth, user, events, admin, api
    
    # Register blueprints
    app.register_blueprint(pages.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(user.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(api.bp)
