"""
Static page routes for cosypolyamory.org

Handles routes for static content pages like home, contact, values, etc.
"""

from flask import Blueprint, render_template, send_file, Response, current_app, request, flash, redirect, url_for
import os
import requests
from cosypolyamory.models.user import User
from cosypolyamory.email import send_email

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


@bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Get form data
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        sender_email = request.form.get('email', '').strip()
        captcha_solution = request.form.get('frc-captcha-solution', '')
        
        # Validate form data
        if not subject or not message or not sender_email:
            flash('Please fill in all required fields.', 'error')
            return render_template("pages/contact.html", page="contact", 
                                 subject=subject, message=message, email=sender_email)
        
        # Validate email format (basic validation)
        if '@' not in sender_email or '.' not in sender_email.split('@')[-1]:
            flash('Please enter a valid email address.', 'error')
            return render_template("pages/contact.html", page="contact", 
                                 subject=subject, message=message, email=sender_email)
        
        # Verify captcha with Friendly Captcha
        captcha_valid = verify_friendly_captcha(captcha_solution)
        if not captcha_valid:
            flash('Please complete the captcha verification.', 'error')
            return render_template("pages/contact.html", page="contact", 
                                 subject=subject, message=message, email=sender_email)
        
        # Send email to all admins and organizers
        try:
            admins_and_organizers = User.select().where(
                (User.is_admin == True) | (User.is_organizer == True)
            )
            
            email_body = f"""
New contact form submission:

From: {sender_email}
Subject: {subject}

Message:
{message}

---
This message was sent via the contact form on cosypolyamory.org
"""
            
            success_count = 0
            for user in admins_and_organizers:
                try:
                    if send_email(user.email, f"Contact Form: {subject}", email_body):
                        success_count += 1
                except Exception as e:
                    current_app.logger.error(f"Failed to send email to {user.email}: {str(e)}")
            
            if success_count > 0:
                flash('Thank you! Your message has been sent to our team.', 'success')
                return redirect(url_for('pages.contact'))
            else:
                flash('Sorry, there was an issue sending your message. Please try again later.', 'error')
                
        except Exception as e:
            current_app.logger.error(f"Contact form error: {str(e)}")
            flash('Sorry, there was an issue sending your message. Please try again later.', 'error')
        
        return render_template("pages/contact.html", page="contact", 
                             subject=subject, message=message, email=sender_email)
    
    # GET request - show the contact form
    site_key = os.getenv('FRIENDLY_CAPTCHA_SITE_KEY', '')
    return render_template("pages/contact.html", page="contact", friendly_captcha_site_key=site_key)


def verify_friendly_captcha(solution):
    """Verify Friendly Captcha solution with their API"""
    if not solution:
        return False
        
    api_key = os.getenv('FRIENDLY_CAPTCHA_API_KEY')
    if not api_key:
        current_app.logger.error("FRIENDLY_CAPTCHA_API_KEY not configured")
        return False
    
    try:
        response = requests.post('https://api.friendlycaptcha.com/api/v1/siteverify', {
            'solution': solution,
            'secret': api_key,
        }, timeout=10)
        
        data = response.json()
        return data.get('success', False)
        
    except Exception as e:
        current_app.logger.error(f"Friendly Captcha verification failed: {str(e)}")
        return False


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
