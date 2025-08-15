"""
Static page routes for cosypolyamory.org

Handles routes for static content pages like home, contact, values, etc.
"""

from flask import Blueprint, render_template, send_file

bp = Blueprint('pages', __name__)


@bp.route('/robots.txt')
def robots_txt():
    return send_file("static/robots.txt")


@bp.route('/sitemap.xml')
def sitemap_xml():
    return send_file("static/sitemap.xml")


@bp.route('/')
def index():
    return render_template("pages/index.html", page="home")


@bp.route('/contact')
def contact():
    return render_template("pages/contact.html", page="contact")


@bp.route('/values')
def values():
    return render_template("pages/values.html", page="values")


@bp.route('/structure')
def rules():
    return render_template("pages/structure.html", page="docs")


@bp.route('/governance')
def governance():
    return render_template("pages/governance.html", page="docs")


@bp.route('/conflict-resolution')
def conflict():
    return send_file("static/pdf/Cosy Polyamory Community - Conflict Resolution Protocol.pdf")


@bp.route('/code-of-conduct')
def coc():
    return render_template("pages/code-of-conduct.html", page="docs")


@bp.route('/events-guide')
def events_guide():
    return render_template("events/events-guide.html", page="docs")
