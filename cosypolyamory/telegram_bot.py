"""
Telegram Bot Module for Cosy Polyamory Community

This module provides a Telegram bot that can be used to make announcements
to the community chat. The bot will be integrated with the main application
to send notifications about events, updates, and other community announcements.
"""

import os
import logging
import asyncio
from typing import Optional, List
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class CosyPolyTelegramBot:
    """
    Telegram bot for the Cosy Polyamory community.
    
    This bot handles announcements and notifications for the community chat.
    """
    
    def __init__(self, token: str, chat_id: Optional[str] = None):
        """
        Initialize the Telegram bot.
        
        Args:
            token: Telegram bot token from BotFather
            chat_id: Default chat ID for announcements (optional)
        """
        self.token = token
        self.chat_id = chat_id
        self.application = None
        self.bot = None
        
        # Initialize Jinja2 template environment
        templates_dir = Path(__file__).parent / "templates" / "telegram"
        self.jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)))
        
    def render_template(self, template_name: str, **context) -> str:
        """
        Render a Jinja2 template with the given context.
        
        Args:
            template_name: Name of the template file
            **context: Template variables
            
        Returns:
            Rendered template string
        """
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            # Fallback to a basic message
            return f"Template rendering failed for {template_name}"
        
    async def initialize(self):
        """Initialize the bot application."""
        try:
            self.application = Application.builder().token(self.token).build()
            self.bot = Bot(token=self.token)
            
            # Add command handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("ping", self.ping_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            
            # Add message handler for testing
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo_handler)
            )
            
            logger.info("Telegram bot initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            return False
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_message = (
            "🌈 Welcome to the Cosy Polyamory community bot! 🌈\n\n"
            "I'm here to help keep you updated with announcements and events.\n\n"
            "Available commands:\n"
            "/help - Show this help message\n"
            "/ping - Check if the bot is alive\n"
            "/status - Show bot status\n"
        )
        await update.message.reply_text(welcome_message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_message = (
            "🤖 Cosy Polyamory Bot Help\n\n"
            "Available commands:\n"
            "• /start - Welcome message and basic info\n"
            "• /help - Show this help message\n"
            "• /ping - Check if the bot is responding\n"
            "• /status - Show current bot status\n\n"
            "This bot will send announcements about:\n"
            "• New events\n"
            "• Event updates and cancellations\n"
            "• Community announcements\n"
            "• System notifications\n"
        )
        await update.message.reply_text(help_message)
    
    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ping command."""
        await update.message.reply_text("🏓 Pong! Bot is alive and well.")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        status_message = (
            "🤖 Bot Status: Online ✅\n"
            f"Chat ID: {update.effective_chat.id}\n"
            f"User: {update.effective_user.first_name}\n"
            "Ready to send announcements! 📢"
        )
        await update.message.reply_text(status_message)
    
    async def echo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages (for testing)."""
        # Only respond to direct messages to avoid spam in groups
        if update.effective_chat.type == 'private':
            await update.message.reply_text(
                f"You said: {update.message.text}\n"
                "Use /help to see available commands."
            )
    
    async def send_announcement(self, message: str, chat_id: Optional[str] = None) -> bool:
        """
        Send an announcement to the specified chat.
        
        Args:
            message: The announcement message to send
            chat_id: Target chat ID (uses default if not provided)
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        target_chat = chat_id or self.chat_id
        
        if not target_chat:
            logger.error("No chat ID specified for announcement")
            return False
        
        # Skip sending if chat ID is a placeholder
        if target_chat in ['your_chat_id_here', 'YOUR_CHAT_ID', '']:
            logger.warning("Chat ID is placeholder value - skipping message send")
            return False
        
        try:
            if not self.bot:
                logger.error("Bot not initialized")
                return False
                
            await self.bot.send_message(
                chat_id=target_chat,
                text=f"📢 **Cosy Telegram Bot Notification**\n\n{message}",
                parse_mode='Markdown'
            )
            logger.info(f"Announcement sent successfully to chat {target_chat}")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send announcement: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending announcement: {e}")
            return False
    
    async def send_templated_announcement(self, message: str, chat_id: Optional[str] = None) -> bool:
        """
        Send a templated announcement using the announcement template.
        
        Args:
            message: The announcement message content
            chat_id: Target chat ID (uses default if not provided)
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        templated_message = self.render_template(
            "announcement.txt",
            message=message
        )
        
        return await self.send_announcement(templated_message, chat_id)
    
    async def send_event_notification(self, event_title: str, event_date: str, 
                                    event_time: str, event_location: str,
                                    event_url: Optional[str] = None,
                                    chat_id: Optional[str] = None) -> bool:
        """
        Send an event notification to the chat.
        
        Args:
            event_title: Title of the event
            event_date: Date of the event
            event_time: Time of the event
            event_location: Location of the event
            event_url: Optional URL to the event details
            chat_id: Target chat ID (uses default if not provided)
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        base_url = os.getenv('DOMAIN', 'https://cosypolyamory.org')
        message = self.render_template(
            "event_created.txt",
            event_title=event_title,
            event_date=event_date,
            event_time=event_time,
            event_location=event_location,
            event_url=event_url or f"{base_url}/events"
        )
        
        return await self.send_announcement(message, chat_id)
    
    async def send_event_update(self, event_title: str, update_type: str,
                              details: str, event_url: Optional[str] = None,
                              chat_id: Optional[str] = None) -> bool:
        """
        Send an event update notification.
        
        Args:
            event_title: Title of the event
            update_type: Type of update (e.g., "CANCELLED", "RESCHEDULED", "UPDATED")
            details: Details about the update
            event_url: Optional URL to the event details
            chat_id: Target chat ID (uses default if not provided)
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        if update_type.upper() == "CANCELLED":
            # Use cancellation template
            message = self.render_template(
                "event_cancelled.txt",
                event_title=event_title,
                cancellation_details=details
            )
        else:
            # Use update template
            base_url = os.getenv('DOMAIN', 'https://cosypolyamory.org')
            message = self.render_template(
                "event_updated.txt",
                event_title=event_title,
                update_details=details,
                event_url=event_url or f"{base_url}/events"
            )
        
        return await self.send_announcement(message, chat_id)
    
    async def start_polling(self):
        """Start the bot with polling."""
        if not self.application:
            logger.error("Bot not initialized. Call initialize() first.")
            return
        
        try:
            logger.info("Starting Telegram bot polling...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            # Keep the bot running
            await self.application.updater.idle()
            
        except Exception as e:
            logger.error(f"Error during polling: {e}")
        finally:
            try:
                if hasattr(self.application.updater, 'stop'):
                    await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as cleanup_error:
                logger.debug(f"Cleanup error (non-critical): {cleanup_error}")
    
    async def start_webhook(self, webhook_url: str, port: int = 8443):
        """Start the bot with webhook (for production)."""
        if not self.application:
            logger.error("Bot not initialized. Call initialize() first.")
            return
        
        try:
            logger.info(f"Starting Telegram bot webhook on {webhook_url}:{port}")
            await self.application.run_webhook(
                listen="0.0.0.0",
                port=port,
                webhook_url=webhook_url
            )
        except Exception as e:
            logger.error(f"Error during webhook setup: {e}")
    
    async def stop(self):
        """Stop the bot gracefully."""
        if self.application:
            try:
                await self.application.stop()
                logger.info("Telegram bot stopped")
            except RuntimeError as e:
                if "not running" in str(e):
                    logger.debug("Bot was already stopped")
                else:
                    logger.error(f"Error stopping bot: {e}")
            except Exception as e:
                logger.error(f"Unexpected error stopping bot: {e}")


# Utility functions for easy integration
async def create_bot_from_env() -> Optional[CosyPolyTelegramBot]:
    """
    Create a bot instance using environment variables.
    
    Expected environment variables:
    - TELEGRAM_BOT_TOKEN: Bot token from BotFather (required)
    - TELEGRAM_CHAT_ID: Default chat ID for announcements (optional)
    
    Returns:
        CosyPolyTelegramBot instance or None if token is missing
    """
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        return None
    
    # Skip placeholder tokens
    if token in ['your_telegram_bot_token_here', 'your_bot_token_here', 'YOUR_BOT_TOKEN']:
        logger.error("TELEGRAM_BOT_TOKEN appears to be a placeholder value")
        return None
    
    # Chat ID is optional for setup purposes
    if not chat_id or chat_id in ['your_chat_id_here', 'YOUR_CHAT_ID']:
        logger.warning("TELEGRAM_CHAT_ID not set or is placeholder - bot can still be used for setup")
        chat_id = None
    
    bot = CosyPolyTelegramBot(token=token, chat_id=chat_id)
    
    if await bot.initialize():
        return bot
    else:
        return None


async def send_quick_announcement(message: str, chat_id: Optional[str] = None) -> bool:
    """
    Quick function to send an announcement without managing bot lifecycle.
    
    Args:
        message: The message to send
        chat_id: Target chat ID (uses env var if not provided)
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    bot = await create_bot_from_env()
    if not bot:
        return False
    
    try:
        result = await bot.send_announcement(message, chat_id)
        await bot.stop()
        return result
    except Exception as e:
        logger.error(f"Error in quick announcement: {e}")
        return False


# Example usage and testing functions
async def test_bot():
    """Test function to verify bot functionality."""
    bot = await create_bot_from_env()
    if not bot:
        print("Failed to create bot. Check your environment variables.")
        return
    
    # Test sending a simple announcement
    success = await bot.send_announcement("🤖 Test announcement from Cosy Polyamory bot!")
    if success:
        print("✅ Test announcement sent successfully!")
    else:
        print("❌ Failed to send test announcement")
    
    # Test sending an event notification
    success = await bot.send_event_notification(
        event_title="Test Event",
        event_date="September 15, 2025",
        event_time="7:00 PM",
        event_location="Community Center",
        event_url="https://example.com/event/123"
    )
    
    if success:
        print("✅ Test event notification sent successfully!")
    else:
        print("❌ Failed to send test event notification")
    
    await bot.stop()


if __name__ == "__main__":
    # Run test if executed directly
    asyncio.run(test_bot())
