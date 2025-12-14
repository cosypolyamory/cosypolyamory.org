"""
Email notification module using Jinja2 templates

This module provides functionality to send notification emails using Jinja2 templates
stored in the templates/notifications directory.
"""

from cosypolyamory.email import send_email, EmailError
from flask import render_template, current_app, url_for
import os
import re
import html


def send_notification_email(to_email: str, template_name: str, **template_vars) -> bool:
    """
    Send a notification email using a Jinja2 template
    
    Args:
        to_email (str): Recipient email address
        template_name (str): Name of the email template to use (without .html extension)
        **template_vars: Variables to pass to the template
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    
    Raises:
        EmailError: If template is not found or email sending fails
    """
    
    # Validate template exists
    template_path = f"notifications/{template_name}.html"
    template_file_path = os.path.join(
        current_app.template_folder if current_app else 'cosypolyamory/templates',
        template_path
    )
    
    if not os.path.exists(template_file_path):
        available_templates = _get_available_templates()
        raise EmailError(f"Template '{template_name}' not found. Available templates: {available_templates}")
    
    try:
        # Render the email template
        html_content = render_template(template_path, **template_vars)
        
        # Extract subject from the rendered template
        subject = _extract_subject_from_html(html_content)
        if not subject:
            raise EmailError(f"Could not extract subject from template '{template_name}'. Make sure the template has a <title> tag or uses {{% block subject %}}.")
        
        # Send the email
        return send_email(to_email, subject, html_content)
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Error sending notification email '{template_name}' to {to_email}: {e}")
        raise EmailError(f"Failed to send notification email: {e}")


def _extract_subject_from_html(html_content: str) -> str:
    """
    Extract the email subject from the rendered HTML template
    
    Args:
        html_content (str): Rendered HTML content
    
    Returns:
        str: Email subject line with HTML entities unescaped
    """
    # Try to extract from <title> tag first
    title_match = re.search(r'<title>(.*?)</title>', html_content, re.DOTALL | re.IGNORECASE)
    if title_match:
        subject = title_match.group(1).strip()
        # Unescape HTML entities (e.g., &amp; -> &, &lt; -> <, &gt; -> >)
        subject = html.unescape(subject)
        subject = re.sub(r'\s*-\s*Cosy Polyamory\s*$', '', subject)
        return subject
    
    return ""


def _get_available_templates() -> list:
    """
    Get list of available notification templates
    
    Returns:
        list: List of available template names (without .html extension)
    """
    try:
        template_dir = os.path.join(
            current_app.template_folder if current_app else 'cosypolyamory/templates',
            'notifications'
        )
        
        if not os.path.exists(template_dir):
            return []
        
        templates = []
        for file in os.listdir(template_dir):
            if file.endswith('.html') and file != 'base.html':
                templates.append(file[:-5])  # Remove .html extension
        
        return sorted(templates)
        
    except Exception:
        return []


def get_template_info() -> dict:
    """
    Get information about available notification templates
    
    Returns:
        dict: Dictionary with template names as keys and their descriptions as values
    """
    return {
        'account_created': 'Welcome email for new user accounts',
        'application_submitted': 'Confirmation email when user submits an application',
        'organizer_new_application': 'Notification to organizers when new application is submitted',
        'rsvp': 'Confirmation email for event attendance',
        'application_approved': 'Welcome email for approved community applications',
        'application_rejected': 'Notification email for rejected applications',
        'event_reminder': 'Reminder email for upcoming events',
        'host_assigned': 'Notification when user is made host/co-host of an event',
        'host_removed': 'Notification when user is removed as host/co-host of an event',
        'rsvp_updated': 'Notification when attendance is updated or waitlisted', 
        'event_updated': 'Notification when an attended event is updated',
        'event_cancelled': 'Notification when an attended event is cancelled'
    }


# High-level notification functions for specific use cases

def notify_application_approved(user):
    """
    Send approval notification email to a user
    
    Args:
        user: User model instance with approved application
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="application_approved",
            name=user.name,
            base_url=current_app.config.get('BASE_URL', 'https://cosypolyamory.org')
        )
        
        if success:
            current_app.logger.info(f"Approval email sent to {user.email}")
        else:
            current_app.logger.warning(f"Failed to send approval email to {user.email}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending approval email to {user.email}: {e}")
        return False


def notify_application_rejected(user, rejection_reason=None):
    """
    Send rejection notification email to a user
    
    Args:
        user: User model instance with rejected application
        rejection_reason: Optional reason for rejection
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="application_rejected",
            name=user.name,
            rejection_reason=rejection_reason
        )
        
        if success:
            current_app.logger.info(f"Rejection email sent to {user.email}")
        else:
            current_app.logger.warning(f"Failed to send rejection email to {user.email}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending rejection email to {user.email}: {e}")
        return False


def send_rsvp_confirmation(user, event, rsvp):
    """
    Send RSVP confirmation email to a user
    
    Args:
        user: User model instance
        event: Event model instance
        rsvp: RSVP model instance
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="rsvp",
            name=user.name,
            event_title=event.title,
            location=event.establishment_name or "Location will be provided to attendees",
            date=event.date.strftime('%A, %B %d, %Y'),
            start_time=event.exact_time.strftime('%I:%M %p') if event.exact_time else "TBD",
            end_time=event.end_time.strftime('%I:%M %p') if event.end_time else None,
            venue_notes=event.location_notes or "",
            event_description=event.description or "",
            event_url=url_for('events.event_detail', event_id=event.id, _external=True)
        )
        
        if success:
            current_app.logger.info(f"RSVP confirmation sent to {user.email} for event: {event.title}")
        else:
            current_app.logger.warning(f"Failed to send RSVP confirmation to {user.email} for event: {event.title}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending RSVP confirmation to {user.email} for event {event.title}: {e}")
        return False


def send_event_reminder(user, event):
    """
    Send event reminder email to a user
    
    Args:
        user: User model instance
        event: Event model instance
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="event_reminder",
            name=user.name,
            event_title=event.title,
            event_date=event.date.strftime('%A, %B %d, %Y'),
            event_time=event.exact_time.strftime('%I:%M %p') if event.exact_time else "TBD",
            event_location=event.establishment_name or "Location will be provided to attendees",
            venue_notes=event.location_notes or "",
            event_description=event.description or "Event details available on the website."
        )
        
        if not success:
            current_app.logger.warning(f"Failed to send event reminder to {user.email} for event: {event.title}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending event reminder to {user.email} for event {event.title}: {e}")
        return False


def send_waitlist_promotion_notification(user, event):
    """
    Send waitlist promotion notification email to a user
    
    Args:
        user: User model instance
        event: Event model instance
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="waitlist_promoted",
            name=user.name,
            event_title=event.title,
            event_date=event.date.strftime('%A, %B %d, %Y'),
            event_time=event.exact_time.strftime('%I:%M %p') if event.exact_time else "TBD",
            event_location=event.establishment_name or "Location will be provided to attendees",
            event_description=event.description or "",
            venue_notes=event.location_notes or "",
            event_url=url_for('events.event_detail', event_id=event.id, _external=True)
        )
        
        if success:
            current_app.logger.info(f"Waitlist promotion notification sent to {user.email} for event: {event.title}")
        else:
            current_app.logger.warning(f"Failed to send waitlist promotion notification to {user.email} for event: {event.title}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending waitlist promotion notification to {user.email} for event {event.title}: {e}")
        return False


def send_rsvp_update_notification(user, event, status, reason=None):
    """
    Send RSVP update notification email to a user
    
    Args:
        user: User model instance
        event: Event model instance
        status: New RSVP status ('yes', 'no', 'maybe', 'waitlist', 'removed')
        reason: Optional reason for the status change
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="rsvp_updated",
            name=user.name,
            event_title=event.title,
            event_date=event.date.strftime('%A, %B %d, %Y'),
            event_time=event.exact_time.strftime('%I:%M %p') if event.exact_time else "TBD",
            event_location=event.establishment_name or "Location will be provided to attendees",
            status=status,
            reason=reason,
            venue_notes=event.location_notes or "",
            event_url=url_for('events.event_detail', event_id=event.id, _external=True)
        )
        
        if success:
            current_app.logger.info(f"RSVP update notification sent to {user.email} for event: {event.title} (status: {status})")
        else:
            current_app.logger.warning(f"Failed to send RSVP update notification to {user.email} for event: {event.title} (status: {status})")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending RSVP update notification to {user.email} for event {event.title}: {e}")
        return False


def notify_host_assigned(user, event, role="host"):
    """
    Send notification when user is assigned as host/co-host of an event
    
    Args:
        user: User model instance
        event: Event model instance
        role: Role assigned ("host" or "co-host")
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="host_assigned",
            name=user.name,
            role=role,
            event_title=event.title,
            event_date=event.date.strftime('%A, %B %d, %Y'),
            event_time=event.exact_time.strftime('%I:%M %p') if event.exact_time else "TBD",
            event_location=event.establishment_name or "Location TBD",
            event_url=url_for('events.event_detail', event_id=event.id, _external=True)
        )
        
        if success:
            current_app.logger.info(f"Host assignment notification sent to {user.email} for event: {event.title}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending host assignment notification to {user.email}: {e}")
        return False


def notify_host_removed(user, event, role="host"):
    """
    Send notification when user is removed as host/co-host of an event
    
    Args:
        user: User model instance
        event: Event model instance
        role: Role removed from ("host" or "co-host")
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="host_removed",
            name=user.name,
            role=role,
            event_title=event.title,
            event_date=event.date.strftime('%A, %B %d, %Y'),
            event_time=event.exact_time.strftime('%I:%M %p') if event.exact_time else "TBD",
            event_location=event.establishment_name or "Location TBD",
            event_url=url_for('events.event_detail', event_id=event.id, _external=True)
        )
        
        if success:
            current_app.logger.info(f"Host removal notification sent to {user.email} for event: {event.title}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending host removal notification to {user.email}: {e}")
        return False


def notify_rsvp_updated(user, event, status, reason=None):
    """
    Send notification when user's RSVP is removed or waitlisted
    
    Args:
        user: User model instance
        event: Event model instance
        status: New status ("removed" or "waitlisted")
        reason: Optional reason for the change
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="rsvp_updated",
            name=user.name,
            status=status,
            event_title=event.title,
            event_date=event.date.strftime('%A, %B %d, %Y'),
            event_time=event.exact_time.strftime('%I:%M %p') if event.exact_time else "TBD",
            event_location=event.establishment_name or "Location TBD",
            reason=reason,
            event_url=url_for('events.event_detail', event_id=event.id, _external=True)
        )
        
        if success:
            current_app.logger.info(f"RSVP update notification sent to {user.email} for event: {event.title}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending RSVP update notification to {user.email}: {e}")
        return False


def notify_event_updated(user, event, changes=None, update_message=None):
    """
    Send notification when an event is updated
    
    Args:
        user: User model instance
        event: Event model instance
        changes: List of changes made to the event
        update_message: Optional message from organizers
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="event_updated",
            name=user.name,
            event_title=event.title,
            event_date=event.date.strftime('%A, %B %d, %Y'),
            event_time=event.exact_time.strftime('%I:%M %p') if event.exact_time else "TBD",
            event_location=event.establishment_name or "Location TBD",
            changes=changes or [],
            update_message=update_message,
            event_url=url_for('events.event_detail', event_id=event.id, _external=True)
        )
        
        if success:
            current_app.logger.info(f"Event update notification sent to {user.email} for event: {event.title}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending event update notification to {user.email}: {e}")
        return False


def notify_account_created(user):
    """
    Send welcome notification email to a newly created user
    
    Args:
        user: User model instance for the new account
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="account_created",
            name=user.name,
            base_url=current_app.config.get('BASE_URL', 'https://cosypolyamory.org')
        )
        
        if success:
            current_app.logger.info(f"Welcome email sent to {user.email}")
        else:
            current_app.logger.warning(f"Failed to send welcome email to {user.email}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending welcome email to {user.email}: {e}")
        return False


def notify_application_submitted(user):
    """
    Send confirmation notification email when a user submits an application
    
    Args:
        user: User model instance who submitted the application
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="application_submitted",
            name=user.name,
            base_url=current_app.config.get('BASE_URL', 'https://cosypolyamory.org')
        )
        
        if success:
            current_app.logger.info(f"Application confirmation email sent to {user.email}")
        else:
            current_app.logger.warning(f"Failed to send application confirmation email to {user.email}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending application confirmation email to {user.email}: {e}")
        return False


def notify_organizers_new_application(user):
    """
    Send notification to all organizers when a new application is submitted
    
    Args:
        user: User model instance who submitted the application
    """
    from cosypolyamory.models.user import User
    from cosypolyamory.models.user_application import UserApplication
    from datetime import datetime
    
    try:
        # Get the user's application
        application = UserApplication.get(UserApplication.user == user)
        questions_and_answers = application.get_questions_and_answers()
        
        # Get all organizers and admins
        organizers = User.select().where(User.role.in_(['admin', 'organizer']))
        
        success_count = 0
        total_count = 0
        
        for organizer in organizers:
            try:
                total_count += 1
                success = send_notification_email(
                    to_email=organizer.email,
                    template_name="organizer_new_application",
                    applicant_name=user.name,
                    applicant_pronouns=user.pronouns,
                    submission_date=datetime.now().strftime('%B %d, %Y at %I:%M %p'),
                    questions_and_answers=questions_and_answers,
                    base_url=current_app.config.get('BASE_URL', 'https://cosypolyamory.org')
                )
                
                if success:
                    success_count += 1
                    current_app.logger.info(f"New application notification sent to organizer {organizer.email}")
                else:
                    current_app.logger.warning(f"Failed to send new application notification to organizer {organizer.email}")
                    
            except EmailError as e:
                current_app.logger.error(f"Error sending new application notification to organizer {organizer.email}: {e}")
            except Exception as e:
                current_app.logger.error(f"Unexpected error sending new application notification to organizer {organizer.email}: {e}")
        
        current_app.logger.info(f"New application notifications: {success_count}/{total_count} sent successfully for user {user.email}")
        return success_count > 0
        
    except UserApplication.DoesNotExist:
        current_app.logger.error(f"Application not found for user {user.email} when trying to notify organizers")
        return False
    except Exception as e:
        current_app.logger.error(f"Error getting application data for organizer notification: {e}")
        return False


def notify_event_cancelled(user, event, cancellation_reason=None, reschedule_info=None, contact_info=None):
    """
    Send notification when an event is cancelled
    
    Args:
        user: User model instance
        event: Event model instance
        cancellation_reason: Reason for cancellation
        reschedule_info: Information about rescheduling
        contact_info: Contact information for questions
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="event_cancelled",
            name=user.name,
            event_title=event.title,
            event_date=event.date.strftime('%A, %B %d, %Y'),
            event_time=event.exact_time.strftime('%I:%M %p') if event.exact_time else "TBD",
            event_location=event.establishment_name,
            cancellation_reason=cancellation_reason,
            reschedule_info=reschedule_info,
            contact_info=contact_info,
            base_url=current_app.config.get('BASE_URL', 'https://cosypolyamory.org')
        )
        
        if success:
            current_app.logger.info(f"Event cancellation notification sent to {user.email} for event: {event.title}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending event cancellation notification to {user.email}: {e}")
        return False
