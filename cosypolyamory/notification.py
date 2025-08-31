from cosypolyamory.email import send_email, EmailError

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
    
    #TODO:
    # You were made host/co-host.
    # Your RSVP was removed/waitlisted.
    # An event you are attending has been updated/cancelled.
    
    templates = {
        'rsvp': {
            'subject': "Cosy Polyamory: You're attending: {event_title} ",
            'body': '''
            <h2>You're attending {event_title}</h2>
            <p>Hello {name},</p>
            <p>You're confirmed to attend {event_title}!</p>
            <p>Location: {location}</p>
            <p>Time: {date}, {start_time} - {end_time}</p>
            <p>Location notes: {location_tips}</p>
            <p>Event details:</br>{event_description}</p>
            <p>For all the details, see here: <a href="{event_url}">{event_url}
            </a></p>
            <p>Best regards,<br>The Cosy Polyamory Team</p>
            '''
        },
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