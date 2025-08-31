"""
Integration examples for using the email module within the Cosy Polyamory Flask application
"""

from cosypolyamory.email import send_email, send_notification_email, EmailError
from flask import current_app


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


def notify_application_rejected(user):
    """
    Send rejection notification email to a user
    
    Args:
        user: User model instance with rejected application
    """
    try:
        success = send_notification_email(
            to_email=user.email,
            template_name="application_rejected",
            name=user.name
        )
        
        if success:
            current_app.logger.info(f"Rejection email sent to {user.email}")
        else:
            current_app.logger.warning(f"Failed to send rejection email to {user.email}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending rejection email to {user.email}: {e}")
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
            event_time=event.start_time.strftime('%I:%M %p'),
            event_location=event.location or "Location will be provided to attendees",
            event_description=event.description or "Event details available on the website."
        )
        
        if success:
            current_app.logger.info(f"Event reminder sent to {user.email} for event: {event.title}")
        else:
            current_app.logger.warning(f"Failed to send event reminder to {user.email} for event: {event.title}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending event reminder to {user.email} for event {event.title}: {e}")
        return False


def send_custom_admin_email(to_email, subject, message):
    """
    Send a custom email from an admin
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        message (str): Email message content
    """
    try:
        # Convert plain text message to simple HTML
        html_message = f"<p>{message.replace(chr(10), '</p><p>')}</p>"
        
        success = send_email(
            to_email=to_email,
            subject=subject,
            body=html_message
        )
        
        if success:
            current_app.logger.info(f"Custom admin email sent to {to_email}: {subject}")
        else:
            current_app.logger.warning(f"Failed to send custom admin email to {to_email}: {subject}")
        
        return success
        
    except EmailError as e:
        current_app.logger.error(f"Error sending custom admin email to {to_email}: {e}")
        return False


# Example usage in routes:
"""
# In your admin routes (e.g., cosypolyamory/routes/admin.py)

from cosypolyamory.email_integration import notify_application_approved, notify_application_rejected

@bp.route('/approve_user/<user_id>')
@admin_required
def approve_user(user_id):
    user = User.get_by_id(user_id)
    user.role = 'approved'
    user.save()
    
    # Send approval email
    notify_application_approved(user)
    
    flash(f'User {user.name} approved and notification email sent!', 'success')
    return redirect(url_for('admin.manage_users'))

@bp.route('/reject_user/<user_id>')
@admin_required
def reject_user(user_id):
    user = User.get_by_id(user_id)
    user.role = 'rejected'
    user.save()
    
    # Send rejection email
    notify_application_rejected(user)
    
    flash(f'User {user.name} rejected and notification email sent!', 'success')
    return redirect(url_for('admin.manage_users'))
"""
