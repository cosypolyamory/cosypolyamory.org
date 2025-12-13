"""
Static page routes for cosypolyamory.org

Handles routes for static content pages like home, contact, values, etc.
"""

from flask import Blueprint, render_template, send_file, Response, current_app, request, flash, redirect, url_for
import os
import requests
from datetime import datetime
from cosypolyamory.models.user import User
from cosypolyamory.models.event import Event
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
            
            # Generate HTML email using template
            email_html = render_template('notifications/contact_us_email.html',
                                       sender_email=sender_email,
                                       subject=subject,
                                       message=message,
                                       timestamp=datetime.now(),
                                       base_url=current_app.config.get('DOMAIN', 'https://cosypolyamory.org'))
            
            success_count = 0
            for user in admins_and_organizers:
                try:
                    if send_email(user.email, f"Contact Form: {subject}", email_html):
                        success_count += 1
                except Exception as e:
                    current_app.logger.error(f"Failed to send email to {user.email}: {str(e)}")
            
            if success_count > 0:
                flash('Thank you! Your message has been sent to our organizers.', 'success')
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


@bp.route('/event/<int:event_id>/feedback', methods=['GET', 'POST'])
def event_feedback(event_id):
    """Event feedback and reporting form"""
    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        flash('Event not found.', 'error')
        return redirect(url_for('pages.index'))
    
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email', '').strip()
        feedback_type = request.form.get('feedback_type', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        anonymous = request.form.get('anonymous') == 'yes'
        captcha_solution = request.form.get('frc-captcha-solution', '')
        
        # Validate form data
        if not feedback_type or not subject or not message:
            flash('Please fill in all required fields.', 'error')
            return render_template("pages/event_feedback.html", page="feedback", 
                                 event=event, email=email, feedback_type=feedback_type,
                                 subject=subject, message=message, anonymous=anonymous,
                                 friendly_captcha_site_key=os.getenv('FRIENDLY_CAPTCHA_SITE_KEY', ''))
        
        # Email is required unless anonymous
        if not anonymous and (not email or '@' not in email or '.' not in email.split('@')[-1]):
            flash('Please enter a valid email address or check the anonymous option.', 'error')
            return render_template("pages/event_feedback.html", page="feedback", 
                                 event=event, email=email, feedback_type=feedback_type,
                                 subject=subject, message=message, anonymous=anonymous,
                                 friendly_captcha_site_key=os.getenv('FRIENDLY_CAPTCHA_SITE_KEY', ''))
        
        # Verify captcha with Friendly Captcha
        captcha_valid = verify_friendly_captcha(captcha_solution)
        if not captcha_valid:
            flash('Please complete the captcha verification.', 'error')
            return render_template("pages/event_feedback.html", page="feedback", 
                                 event=event, email=email, feedback_type=feedback_type,
                                 subject=subject, message=message, anonymous=anonymous,
                                 friendly_captcha_site_key=os.getenv('FRIENDLY_CAPTCHA_SITE_KEY', ''))
        
        # Send email to all admins and organizers
        try:
            admins_and_organizers = User.select().where(
                (User.is_admin == True) | (User.is_organizer == True)
            )
            
            # Generate HTML email using template
            email_html = render_template('notifications/event_feedback_email.html',
                                       event_title=event.title,
                                       event_date=event.exact_time.strftime('%A, %B %d, %Y at %I:%M %p'),
                                       event_location=event.establishment_name if event.establishment_name else None,
                                       sender_email=email if not anonymous else 'Anonymous',
                                       feedback_type=feedback_type,
                                       subject=subject,
                                       message=message,
                                       is_anonymous=anonymous,
                                       timestamp=datetime.now(),
                                       base_url=current_app.config.get('DOMAIN', 'https://cosypolyamory.org'))
            
            # Create email subject with priority indicator
            priority_prefix = "🚨 URGENT - " if feedback_type in ['concern', 'violation'] else ""
            email_subject = f"{priority_prefix}Event Feedback: {event.title} - {feedback_type.title()}"
            
            success_count = 0
            for user in admins_and_organizers:
                try:
                    if send_email(user.email, email_subject, email_html):
                        success_count += 1
                except Exception as e:
                    current_app.logger.error(f"Failed to send email to {user.email}: {str(e)}")
            
            if success_count > 0:
                feedback_verb = "reported" if feedback_type in ['concern', 'violation'] else "submitted"
                flash(f'Thank you! Your feedback has been {feedback_verb}. Our team will review it promptly.', 'success')
                return redirect(url_for('events.event_detail', event_id=event.id))
            else:
                flash('Sorry, there was an issue sending your feedback. Please try again later.', 'error')
                
        except Exception as e:
            current_app.logger.error(f"Event feedback error: {str(e)}")
            flash('Sorry, there was an issue sending your feedback. Please try again later.', 'error')
        
        return render_template("pages/event_feedback.html", page="feedback", 
                             event=event, email=email, feedback_type=feedback_type,
                             subject=subject, message=message, anonymous=anonymous,
                             friendly_captcha_site_key=os.getenv('FRIENDLY_CAPTCHA_SITE_KEY', ''))
    
    # GET request - show the feedback form
    site_key = os.getenv('FRIENDLY_CAPTCHA_SITE_KEY', '')
    return render_template("pages/event_feedback.html", page="feedback", 
                         event=event, friendly_captcha_site_key=site_key)
