"""
Integration module for connecting the Telegram bot with the Cosy Polyamory application.

This module provides functions to send notifications from the main app to the Telegram bot.
"""

import asyncio
import logging
from typing import Optional
from cosypolyamory.telegram_bot import send_quick_announcement, create_bot_from_env

logger = logging.getLogger(__name__)


class TelegramNotificationService:
    """Service for sending notifications via Telegram bot."""
    
    def __init__(self):
        self.enabled = True
        self._check_configuration()
    
    def _check_configuration(self):
        """Check if Telegram bot is properly configured."""
        import os
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not token or token in ['your_telegram_bot_token_here', 'your_bot_token_here', 'YOUR_BOT_TOKEN']:
            logger.warning("Telegram bot not configured - TELEGRAM_BOT_TOKEN missing or placeholder")
            self.enabled = False
        elif not chat_id or chat_id in ['your_chat_id_here', 'YOUR_CHAT_ID', '']:
            logger.warning("Telegram chat ID not configured - notifications will not be sent")
            self.enabled = False
    
    async def send_event_created_notification(self, event) -> bool:
        """
        Send notification when a new event is created.
        
        Args:
            event: Event model instance
            
        Returns:
            bool: True if notification sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            bot = await create_bot_from_env()
            if not bot:
                return False
            
            event_url = f"https://cosypolyamory.org/events/{event.id}"
            success = await bot.send_event_notification(
                event_title=event.title,
                event_date=event.date.strftime('%A, %B %d, %Y'),
                event_time=event.exact_time.strftime('%I:%M %p') if event.exact_time else "TBD",
                event_location=event.establishment_name or event.barrio,
                event_url=event_url
            )
            
            await bot.stop()
            return success
            
        except Exception as e:
            logger.error(f"Failed to send event created notification: {e}")
            return False
    
    async def send_event_updated_notification(self, event, update_details: str) -> bool:
        """
        Send notification when an event is updated.
        
        Args:
            event: Event model instance
            update_details: Description of what was updated
            
        Returns:
            bool: True if notification sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            bot = await create_bot_from_env()
            if not bot:
                return False
            
            event_url = f"https://cosypolyamory.org/events/{event.id}"
            success = await bot.send_event_update(
                event_title=event.title,
                update_type="UPDATED",
                details=update_details,
                event_url=event_url
            )
            
            await bot.stop()
            return success
            
        except Exception as e:
            logger.error(f"Failed to send event updated notification: {e}")
            return False
    
    async def send_event_cancelled_notification(self, event, reason: str = "") -> bool:
        """
        Send notification when an event is cancelled.
        
        Args:
            event: Event model instance
            reason: Reason for cancellation
            
        Returns:
            bool: True if notification sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            bot = await create_bot_from_env()
            if not bot:
                return False
            
            details = f"Unfortunately, this event has been cancelled."
            if reason:
                details += f"\n\nReason: {reason}"
            
            success = await bot.send_event_update(
                event_title=event.title,
                update_type="CANCELLED",
                details=details
            )
            
            await bot.stop()
            return success
            
        except Exception as e:
            logger.error(f"Failed to send event cancelled notification: {e}")
            return False
    
    async def send_event_reminder(self, event, hours_before: int = 24) -> bool:
        """
        Send event reminder notification.
        
        Args:
            event: Event model instance
            hours_before: How many hours before the event this reminder is sent
            
        Returns:
            bool: True if notification sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            bot = await create_bot_from_env()
            if not bot:
                return False
            
            time_text = f"{hours_before} hours" if hours_before != 1 else "1 hour"
            details = (
                f"Don't forget! This event is happening in {time_text}.\n\n"
                f"📅 {event.date.strftime('%A, %B %d, %Y')}\n"
                f"🕐 {event.exact_time.strftime('%I:%M %p') if event.exact_time else 'TBD'}\n"
                f"📍 {event.establishment_name or event.barrio}\n\n"
                "See you there! 💕"
            )
            
            success = await bot.send_event_update(
                event_title=event.title,
                update_type="REMINDER",
                details=details
            )
            
            await bot.stop()
            return success
            
        except Exception as e:
            logger.error(f"Failed to send event reminder: {e}")
            return False
    
    async def send_custom_announcement(self, message: str) -> bool:
        """
        Send a custom announcement message.
        
        Args:
            message: The announcement message
            
        Returns:
            bool: True if notification sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            return await send_quick_announcement(message)
        except Exception as e:
            logger.error(f"Failed to send custom announcement: {e}")
            return False
    
    def send_event_created_sync(self, event) -> bool:
        """Synchronous wrapper for event created notification."""
        try:
            # Create a new event loop for this thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(self.send_event_created_notification(event))
        except Exception as e:
            logger.error(f"Error in sync event created notification: {e}")
            return False
    
    def send_event_updated_sync(self, event, update_details: str) -> bool:
        """Synchronous wrapper for event updated notification."""
        try:
            # Create a new event loop for this thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(self.send_event_updated_notification(event, update_details))
        except Exception as e:
            logger.error(f"Error in sync event updated notification: {e}")
            return False
    
    def send_event_cancelled_sync(self, event, reason: str = "") -> bool:
        """Synchronous wrapper for event cancelled notification."""
        try:
            # Create a new event loop for this thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(self.send_event_cancelled_notification(event, reason))
        except Exception as e:
            logger.error(f"Error in sync event cancelled notification: {e}")
            return False
    
    def send_custom_announcement_sync(self, message: str) -> bool:
        """Synchronous wrapper for custom announcement."""
        try:
            # Create a new event loop for this thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(self.send_custom_announcement(message))
        except Exception as e:
            logger.error(f"Error in sync custom announcement: {e}")
            return False


# Global instance for easy access
telegram_service = TelegramNotificationService()


# Convenience functions for easy integration
def notify_event_created(event) -> bool:
    """Convenience function to notify about new event creation."""
    return telegram_service.send_event_created_sync(event)


def notify_event_updated(event, update_details: str) -> bool:
    """Convenience function to notify about event updates."""
    return telegram_service.send_event_updated_sync(event, update_details)


def notify_event_cancelled(event, reason: str = "") -> bool:
    """Convenience function to notify about event cancellation."""
    return telegram_service.send_event_cancelled_sync(event, reason)


def send_announcement(message: str) -> bool:
    """Convenience function to send custom announcements."""
    return telegram_service.send_custom_announcement_sync(message)


# Example integration points (to be added to existing code later)
"""
Integration examples:

1. In event creation route:
   from cosypolyamory.telegram_integration import notify_event_created
   
   # After creating event
   notify_event_created(event)

2. In event update route:
   from cosypolyamory.telegram_integration import notify_event_updated
   
   # After updating event
   notify_event_updated(event, "Event time has been changed to 8:00 PM")

3. In event deletion route:
   from cosypolyamory.telegram_integration import notify_event_cancelled
   
   # Before deleting event
   notify_event_cancelled(event, "Low attendance")

4. For custom announcements:
   from cosypolyamory.telegram_integration import send_announcement
   
   send_announcement("Welcome new members! Please read our community guidelines.")
"""
