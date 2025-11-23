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

    # Don't send testing emails 
    if to_email.lower().endswith("example.net") or to_email.lower().endswith("example.com"):
        return True
    
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


def send_email_verification(user, new_email: str, verification_url: str, hours_valid: int = 24) -> bool:
    """
    Send an email verification message
    
    Args:
        user: User object
        new_email: The new email address to verify
        verification_url: The verification URL with token
        hours_valid: Number of hours the link is valid (default: 24)
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    from flask import render_template
    
    subject = "Verify Your Email Address - Cosy Polyamory"
    
    # Render the email template
    body = render_template(
        'notifications/email_verification.html',
        user_name=user.name,
        new_email=new_email,
        verification_url=verification_url,
        hours_valid=hours_valid
    )
    
    try:
        return send_email(new_email, subject, body)
    except EmailError as e:
        current_app.logger.error(f"Failed to send verification email to {new_email}: {e}")
        return False


if __name__ == "__main__":
    # Run configuration test when module is executed directly
    test_email_configuration()
