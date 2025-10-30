#!/usr/bin/env python3
"""
Event Reminder Service

This script runs in an infinite loop, waking up once a minute to check if midnight has passed.
If so, and only once a day, it sends reminders to all people who have confirmed attendance 
or are on the waitlist for any event happening that day.

Usage:
    python send_event_reminders.py

The script uses a simple file-based mechanism to track when it last ran, storing the date
in a file called .last_reminder_run
"""

import os
import sys
import time
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

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
CHECK_INTERVAL_SECONDS = 60  # Check every minute
REMINDER_HOUR = 0  # Send reminders at midnight (24:00 / 00:00)
REMINDER_MINUTE = 0

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_last_run_date():
    """
    Get the date when reminders were last sent.
    
    Returns:
        date or None: The last run date, or None if never run
    """
    try:
        if os.path.exists(LAST_RUN_FILE):
            with open(LAST_RUN_FILE, 'r') as f:
                date_str = f.read().strip()
                return datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception as e:
        logger.warning(f"Error reading last run file: {e}")
    return None


def set_last_run_date(run_date):
    """
    Store the date when reminders were last sent.
    
    Args:
        run_date (date): The date to store
    """
    try:
        with open(LAST_RUN_FILE, 'w') as f:
            f.write(run_date.strftime('%Y-%m-%d'))
        logger.info(f"Updated last run date to {run_date}")
    except Exception as e:
        logger.error(f"Error writing last run file: {e}")


def should_send_reminders():
    """
    Determine if reminders should be sent today.
    
    Returns:
        bool: True if reminders should be sent, False otherwise
    """
    today = date.today()
    last_run = get_last_run_date()
    
    # If we've never run, or if it's a new day since last run
    if last_run is None:
        logger.info("No previous run found - will send reminders")
        return True
    
    if today > last_run:
        logger.info(f"New day detected (last run: {last_run}, today: {today}) - will send reminders")
        return True
    
    logger.debug(f"Already sent reminders today ({today})")
    return False


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


def is_reminder_time():
    """
    Check if it's the right time to send reminders (just after midnight).
    
    Returns:
        bool: True if it's time to send reminders
    """
    now = datetime.now()
    return now.hour == REMINDER_HOUR and now.minute == REMINDER_MINUTE


def main():
    """
    Main loop that runs continuously, checking for reminder time.
    """
    logger.info("Starting Event Reminder Service")
    logger.info(f"Will check every {CHECK_INTERVAL_SECONDS} seconds for reminder time ({REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d})")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"Last run tracking file: {LAST_RUN_FILE}")
    
    while True:
        try:
            current_time = datetime.now()
            
            # Check if it's reminder time and we haven't sent today
            if is_reminder_time() and should_send_reminders():
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
            
            else:
                # Log current status every hour for monitoring
                if current_time.minute == 0:
                    last_run = get_last_run_date()
                    logger.debug(f"Service running. Current time: {current_time.strftime('%H:%M')}, "
                               f"Last run: {last_run or 'Never'}")
            
            # Sleep until next check
            time.sleep(CHECK_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            logger.info(f"Continuing after error, sleeping {CHECK_INTERVAL_SECONDS} seconds...")
            time.sleep(CHECK_INTERVAL_SECONDS)


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