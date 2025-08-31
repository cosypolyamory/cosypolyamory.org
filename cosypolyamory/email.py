"""
Email module for sending emails via Mailtrap API

This module provides functionality to send emails using the Mailtrap API service.
"""

import os
import requests
from typing import Optional
from flask import current_app


class EmailError(Exception):
    """Custom exception for email-related errors"""
    pass


def send_email(to_email: str, subject: str, body: str, from_email: Optional[str] = None) -> bool:
    """
    Send an email via Mailtrap API
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject line
        body (str): Email body content (can be HTML or plain text)
        from_email (str, optional): Sender email address. If not provided, uses default from environment
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    
    Raises:
        EmailError: If there's an error with email configuration or sending
    """
    
    # Get Mailtrap configuration from environment variables
    api_token = os.getenv('MAILTRAP_API_TOKEN')
    if not api_token:
        raise EmailError("MAILTRAP_API_TOKEN environment variable is not set")
    
    # Default sender email
    if not from_email:
        from_email = os.getenv('MAILTRAP_FROM_EMAIL', 'noreply@cosypolyamory.org')
    
    # Mailtrap API endpoint
    url = "https://send.api.mailtrap.io/api/send"
    
    # Prepare email data
    email_data = {
        "from": {
            "email": from_email,
            "name": "Cosy Polyamory Community"
        },
        "to": [
            {
                "email": to_email
            }
        ],
        "subject": subject,
        "html": body,  # Mailtrap accepts HTML content
        "text": _strip_html(body)  # Also provide plain text version
    }
    
    # Headers for the API request
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Send the email via Mailtrap API
        response = requests.post(url, json=email_data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Log successful send (optional)
            if current_app:
                current_app.logger.info(f"Email sent successfully to {to_email} with subject: {subject}")
            return True
        else:
            # Log error details
            error_msg = f"Failed to send email to {to_email}. Status: {response.status_code}, Response: {response.text}"
            if current_app:
                current_app.logger.error(error_msg)
            raise EmailError(error_msg)
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error while sending email to {to_email}: {str(e)}"
        if current_app:
            current_app.logger.error(error_msg)
        raise EmailError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error while sending email to {to_email}: {str(e)}"
        if current_app:
            current_app.logger.error(error_msg)
        raise EmailError(error_msg)


def send_notification_email(to_email: str, template_name: str, **template_vars) -> bool:
    """
    Send a notification email using a predefined template
    
    Args:
        to_email (str): Recipient email address
        template_name (str): Name of the email template to use
        **template_vars: Variables to substitute in the template
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    
    templates = {
        'application_approved': {
            'subject': 'Welcome to Cosy Polyamory Community! 🎉',
            'body': '''
            <h2>Congratulations! Your application has been approved</h2>
            <p>Hello {name},</p>
            <p>We're excited to welcome you to the Cosy Polyamory Community! Your application has been reviewed and approved.</p>
            <p>You now have full access to:</p>
            <ul>
                <li>All community events and their details</li>
                <li>RSVP functionality for events</li>
                <li>Community member connections</li>
                <li>Private event locations and information</li>
            </ul>
            <p>Visit <a href="{base_url}/events">our events page</a> to see what's coming up!</p>
            <p>Welcome to the community!</p>
            <p>Best regards,<br>The Cosy Polyamory Team</p>
            '''
        },
        'application_rejected': {
            'subject': 'Update on your Cosy Polyamory Community application',
            'body': '''
            <h2>Application Update</h2>
            <p>Hello {name},</p>
            <p>Thank you for your interest in joining the Cosy Polyamory Community.</p>
            <p>After careful review, we've decided not to approve your application at this time. This decision is based on ensuring the best fit for our community culture and values.</p>
            <p>You're welcome to reapply in the future if your circumstances change.</p>
            <p>Best regards,<br>The Cosy Polyamory Team</p>
            '''
        },
        'event_reminder': {
            'subject': 'Reminder: {event_title} is coming up!',
            'body': '''
            <h2>Event Reminder</h2>
            <p>Hello {name},</p>
            <p>This is a friendly reminder that you're signed up for:</p>
            <h3>{event_title}</h3>
            <p><strong>When:</strong> {event_date} at {event_time}</p>
            <p><strong>Where:</strong> {event_location}</p>
            <p>{event_description}</p>
            <p>We're looking forward to seeing you there!</p>
            <p>Best regards,<br>The Cosy Polyamory Team</p>
            '''
        }
    }
    
    if template_name not in templates:
        raise EmailError(f"Unknown email template: {template_name}")
    
    template = templates[template_name]
    subject = template['subject'].format(**template_vars)
    body = template['body'].format(**template_vars)
    
    return send_email(to_email, subject, body)


def _strip_html(html_content: str) -> str:
    """
    Simple HTML tag stripper for plain text email content
    
    Args:
        html_content (str): HTML content to strip
    
    Returns:
        str: Plain text content
    """
    import re
    
    # Remove HTML tags
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', html_content)
    
    # Clean up whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Replace multiple newlines with double newlines
    text = text.strip()
    
    return text


def test_email_configuration() -> bool:
    """
    Test if email configuration is working properly
    
    Returns:
        bool: True if configuration is valid and can send emails
    """
    try:
        api_token = os.getenv('MAILTRAP_API_TOKEN')
        if not api_token:
            print("❌ MAILTRAP_API_TOKEN environment variable is not set")
            return False
        
        from_email = os.getenv('MAILTRAP_FROM_EMAIL', 'noreply@cosypolyamory.org')
        print(f"✅ Mailtrap configuration found")
        print(f"   API Token: {'*' * (len(api_token) - 4) + api_token[-4:]}")
        print(f"   From Email: {from_email}")
        
        # You can uncomment the line below to send a test email
        # send_email("test@example.com", "Test Email", "<h1>Test</h1><p>This is a test email.</p>")
        
        return True
        
    except Exception as e:
        print(f"❌ Email configuration test failed: {e}")
        return False


if __name__ == "__main__":
    # Run configuration test when module is executed directly
    test_email_configuration()
