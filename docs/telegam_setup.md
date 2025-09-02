# Cosy Polyamory Telegram Bot

This module provides a Telegram bot for the Cosy Polyamory community that can send announcements, event notifications, and other community updates to a Telegram chat.

## Features

- 🤖 **Bot Commands**: `/start`, `/help`, `/ping`, `/status`
- 📢 **Announcements**: Send custom announcements to the community
- 🎉 **Event Notifications**: Automatic notifications for new events, updates, and cancellations
- ⏰ **Event Reminders**: Send reminders before events
- 🔧 **Easy Integration**: Simple API for connecting with the main application

## Setup

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the instructions
3. Choose a name and username for your bot
4. Copy the bot token provided by BotFather

### 2. Get Chat ID

1. Add your bot to the community chat or group
2. Make sure the bot has permission to send messages
3. Send a message to the chat mentioning the bot
4. Use one of these methods to get the chat ID:
   - Send `/status` command to the bot in the chat
   - Use the `telegram_bot_manager.py chat_id` command
   - Check bot logs when running in polling mode

or make a call to:

https://api.telegram.org/bot<token>/getUpdates

And then find chat id in the JSON data.

### 3. Configure Environment Variables

Add these variables to your `.env` file:

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 4. Install Dependencies

The bot requires the `python-telegram-bot` library, which is already added to `requirements.txt`.

```bash
pip install python-telegram-bot
```

## Usage

### Command Line Interface

The `telegram_bot_manager.py` script provides a CLI for managing the bot:

```bash
# Interactive setup guide
python telegram_bot_manager.py setup

# Test bot connection
python telegram_bot_manager.py test

# Get chat ID for configuration
python telegram_bot_manager.py chat_id

# Send test announcement
python telegram_bot_manager.py announce

# Send test event notification
python telegram_bot_manager.py event

# Run bot in polling mode (for development/testing)
python telegram_bot_manager.py run
```

### Integration with Main Application

The bot integrates with the main application through the `telegram_integration.py` module:

```python
from cosypolyamory.telegram_integration import (
    notify_event_created,
    notify_event_updated,
    notify_event_cancelled,
    send_announcement
)

# Notify about new event
notify_event_created(event)

# Notify about event updates
notify_event_updated(event, "Time changed to 8:00 PM")

# Notify about cancellation
notify_event_cancelled(event, "Low attendance")

# Send custom announcement
send_announcement("Welcome new members!")
```

### Direct Bot Usage

You can also use the bot directly:

```python
import asyncio
from cosypolyamory.telegram_bot import CosyPolyTelegramBot

async def example():
    bot = CosyPolyTelegramBot(token="your_token", chat_id="your_chat_id")
    await bot.initialize()
    
    # Send announcement
    await bot.send_announcement("Hello community!")
    
    # Send event notification
    await bot.send_event_notification(
        event_title="Community Meetup",
        event_date="September 15, 2025",
        event_time="7:00 PM",
        event_location="Community Center",
        event_url="https://example.com/event"
    )
    
    await bot.stop()

# Run the example
asyncio.run(example())
```

## Bot Commands

When users interact with the bot in Telegram, they can use these commands:

- `/start` - Welcome message and basic information
- `/help` - Show available commands and bot features
- `/ping` - Check if bot is responding
- `/status` - Show bot status and current chat ID

## Message Types

### Announcements
Basic announcements with the community branding:
```
📢 **Cosy Polyamory Announcement**

Your message here
```

### Event Notifications
Rich event notifications with all details:
```
🎉 **New Event Alert!** 🎉

**Community Meetup**
📅 September 15, 2025
🕐 7:00 PM
📍 Community Center

🔗 [View Event Details](https://example.com/event)

See you there! 💕
```

### Event Updates
Notifications for changes, cancellations, or reminders:
```
❌ **Event Cancelled** ❌

**Community Meetup**

Unfortunately, this event has been cancelled.

Reason: Low attendance
```

## Development

### Testing

Use the manager script to test functionality:

```bash
# Test connection and basic functionality
python telegram_bot_manager.py test

# Send test messages
python telegram_bot_manager.py announce
python telegram_bot_manager.py event
```

### Running in Development

For development and testing, you can run the bot in polling mode:

```bash
python telegram_bot_manager.py run
```

This will start the bot and listen for commands. Press Ctrl+C to stop.

### Production Deployment

For production, you'll want to integrate the bot notifications into your main application flow rather than running it as a separate polling service.

The `telegram_integration.py` module provides synchronous wrappers that can be called from your Flask routes without blocking the web application.

## Error Handling

The bot includes comprehensive error handling:

- **Missing Configuration**: Bot gracefully disables if tokens/chat IDs are missing
- **Network Errors**: Telegram API errors are caught and logged
- **Async/Sync Compatibility**: Both async and sync interfaces provided
- **Logging**: All operations are logged for debugging

## Security Considerations

- **Token Security**: Keep your bot token secure and never commit it to version control
- **Chat Permissions**: Ensure the bot only has necessary permissions in your chat
- **Rate Limiting**: Telegram has rate limits - the bot handles basic rate limiting
- **Message Content**: Be mindful of what information you include in public announcements

## Future Enhancements

Potential improvements for the bot:

- **Interactive Commands**: Allow community members to interact with the bot
- **RSVP Integration**: Let users RSVP to events directly through Telegram
- **Scheduled Messages**: Schedule announcements for specific times
- **Multiple Chats**: Support for multiple community chats
- **Rich Media**: Support for images, documents, and other media types
- **Webhook Mode**: Production webhook support for better performance

## Troubleshooting

### Bot Not Responding
1. Check that `TELEGRAM_BOT_TOKEN` is correct
2. Verify the bot is added to the chat
3. Ensure the bot has permission to send messages
4. Check logs for error messages

### Messages Not Sent
1. Verify `TELEGRAM_CHAT_ID` is correct
2. Check that the chat still exists
3. Ensure the bot wasn't removed from the chat
4. Check network connectivity

### Command Issues
1. Make sure you're using the correct command format
2. Try the `/help` command to see available options
3. Check that you're in the right chat
4. Restart the bot if it seems unresponsive

For more help, check the application logs or run the test commands to diagnose issues.
