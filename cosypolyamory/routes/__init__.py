"""
Route registration for cosypolyamory.org

This module registers all blueprint routes with the Flask application.
"""

def register_routes(app):
    """Register all application blueprints"""
    
    # Import blueprints
    from . import pages, auth, user, events, admin
    from .api import bp as api_bp
    
    # Register main blueprints
    app.register_blueprint(pages.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(user.bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(admin.bp)
