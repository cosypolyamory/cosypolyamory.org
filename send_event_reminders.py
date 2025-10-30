#!/usr/bin/env python3
"""
Event Reminder Service

This script uses the `schedule` library to send daily event reminders at midnight.
It sends reminders to all people who have confirmed attendance or are on the waitlist 
for any event happening that day.

Usage:
    python send_event_reminders.py

The script uses a simple file-based mechanism to track when it last ran, storing the date
in a file called .last_reminder_run to prevent duplicate sends.
"""

import os
import sys
import time
import logging
import schedule
from datetime import datetime, date, timedelta

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import Flask app and models
from cosypolyamory.app import app
from cosypolyamory.models.event import Event
from cosypolyamory.models.rsvp import RSVP
from cosypolyamory.models.user import User
from cosypolyamory.notification import send_event_reminder

# Configuration
LAST_RUN_FILE = os.path.join(project_root, '.last_reminder_run')
LOG_FILE = os.path.join(project_root, 'event_reminders.log')
REMINDER_TIME = "23:49"  # Send reminders at midnight

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)


def get_events_for_today():
    """
    Get all events happening today.
    
    Returns:
        list: List of Event objects happening today
    """
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())
    
    try:
        events = list(Event.select().where(
            (Event.exact_time >= start_of_day) & 
            (Event.exact_time <= end_of_day) &
            (Event.is_active == True)
        ))
        
        logger.info(f"Found {len(events)} events for today ({today})")
        return events
    
    except Exception as e:
        logger.error(f"Error querying events for today: {e}")
        return []


def get_attendees_for_event(event):
    """
    Get all users who should receive reminders for an event.
    This includes users with status 'yes' (attending) or 'waitlist'.
    
    Args:
        event (Event): The event to get attendees for
        
    Returns:
        list: List of User objects who should receive reminders
    """
    try:
        # Get RSVPs for users who are attending or waitlisted
        rsvps = list(RSVP.select(RSVP, User).join(User).where(
            (RSVP.event == event) & 
            (RSVP.status.in_(['yes', 'waitlist']))
        ))
        
        attendees = [rsvp.user for rsvp in rsvps]
        logger.info(f"Found {len(attendees)} attendees for event '{event.title}'")
        return attendees
    
    except Exception as e:
        logger.error(f"Error querying attendees for event {event.title}: {e}")
        return []


def send_reminders_for_today():
    """
    Send event reminders for all events happening today.
    
    Returns:
        dict: Summary of reminders sent
    """
    summary = {
        'events_processed': 0,
        'reminders_sent': 0,
        'reminders_failed': 0,
        'errors': []
    }
    
    events = get_events_for_today()
    
    for event in events:
        summary['events_processed'] += 1
        logger.info(f"Processing event: {event.title} at {event.exact_time}")
        
        attendees = get_attendees_for_event(event)
        
        for user in attendees:
            try:
                # Send reminder within Flask app context
                with app.app_context():
                    success = send_event_reminder(user, event)
                    
                if success:
                    summary['reminders_sent'] += 1
                    logger.info(f"Sent reminder to {user.email} for {event.title}")
                else:
                    summary['reminders_failed'] += 1
                    logger.warning(f"Failed to send reminder to {user.email} for {event.title}")
                    
            except Exception as e:
                summary['reminders_failed'] += 1
                error_msg = f"Error sending reminder to {user.email} for {event.title}: {e}"
                logger.error(error_msg)
                summary['errors'].append(error_msg)
    
    return summary


def send_daily_reminders():
    """
    Job function to be called by the scheduler to send daily reminders.
    """

    try:
        logger.info("=== Starting daily reminder process ===")
        
        summary = send_reminders_for_today()
        
        # Update the last run date
        set_last_run_date(date.today())
        
        logger.info("=== Daily reminder process completed ===")
        logger.info(f"Summary: {summary['events_processed']} events processed, "
                   f"{summary['reminders_sent']} reminders sent, "
                   f"{summary['reminders_failed']} failed")
        
        if summary['errors']:
            logger.error(f"Errors encountered: {summary['errors']}")
            
    except Exception as e:
        logger.error(f"Error in daily reminder job: {e}")


def main():
    """
    Main function that sets up the scheduler and runs the reminder service.
    """
    logger.info("Starting Event Reminder Service with schedule library")
    logger.info(f"Reminders scheduled for {REMINDER_TIME} each day")
    
    # Schedule the daily reminder job
    schedule.every().day.at(REMINDER_TIME).do(send_daily_reminders)
    
    logger.info(f"Job scheduled successfully. Next run: {schedule.next_run()}")
    
    # Main scheduling loop
    while True:
        try:
            logger.info("woke!")
            schedule.run_pending()
            time.sleep(15)  # Check every minute
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in scheduler loop: {e}")
            logger.info("Continuing after error...")
            time.sleep(60)


if __name__ == "__main__":
    # Ensure we can import the Flask app
    try:
        with app.app_context():
            # Test database connection
            event_count = Event.select().count()
            logger.info(f"Successfully connected to database. Found {event_count} events total.")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        logger.error("Please ensure the database is set up and accessible.")
        sys.exit(1)
    
    main()
