"""
Static page routes for cosypolyamory.org

Handles routes for static content pages like home, contact, values, etc.
"""

from flask import Blueprint, render_template, send_file, Response, current_app
import os

bp = Blueprint('pages', __name__)


@bp.route('/robots.txt')
def robots_txt():
    base_url = current_app.config.get('BASE_URL', 'https://cosypolyamory.org')
    content = f"""User-agent: *
Allow: /

Sitemap: {base_url}/sitemap.xml
"""
    return Response(content, mimetype='text/plain')


@bp.route('/sitemap.xml')
def sitemap_xml():
    base_url = current_app.config.get('BASE_URL', 'https://cosypolyamory.org')
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>{base_url}/</loc><lastmod>2025-01-20T15:08:08+00:00</lastmod><priority>1.00</priority></url>
<url><loc>{base_url}/values</loc><lastmod>2025-01-20T15:08:08+00:00</lastmod><priority>0.80</priority></url>
<url><loc>{base_url}/contact</loc><lastmod>2025-01-20T15:08:08+00:00</lastmod><priority>0.80</priority></url>
<url><loc>{base_url}/team</loc><lastmod>2025-01-20T15:08:08+00:00</lastmod><priority>0.80</priority></url>
</urlset>
"""
    return Response(content, mimetype='application/xml')


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
