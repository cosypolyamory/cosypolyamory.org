"""
Configuration and management script for the Cosy Polyamory Telegram Bot.

This script provides utilities for setting up, testing, and managing the Telegram bot.
"""

import os
import sys
import asyncio
import argparse
from typing import Optional
from dotenv import load_dotenv
from cosypolyamory.telegram_bot import CosyPolyTelegramBot, create_bot_from_env

# Load environment variables
load_dotenv()


async def setup_bot_interactive():
    """Interactive setup for bot configuration."""
    print("🤖 Cosy Polyamory Telegram Bot Setup")
    print("=" * 40)
    
    # Check for existing configuration
    existing_token = os.getenv('TELEGRAM_BOT_TOKEN')
    existing_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if existing_token and existing_token not in ['your_telegram_bot_token_here', 'your_bot_token_here']:
        print(f"✅ Found bot token: {existing_token[:10]}...")
    else:
        print("❌ No valid bot token found")
    
    if existing_chat_id and existing_chat_id not in ['your_chat_id_here', 'YOUR_CHAT_ID']:
        print(f"✅ Found chat ID: {existing_chat_id}")
    else:
        print("❌ No valid chat ID found")
    
    print("\n📋 Setup Steps:")
    print("=" * 15)
    
    print("\n1️⃣  CREATE TELEGRAM BOT:")
    print("   • Message @BotFather on Telegram")
    print("   • Send '/newbot' and follow instructions")
    print("   • Copy the bot token")
    print("   • Add to .env file: TELEGRAM_BOT_TOKEN=your_token_here")
    
    print("\n2️⃣  DISCOVER CHAT ID:")
    print("   • Run: python telegram_bot_manager.py chat_id")
    print("   • Send any message to your bot (private or group)")
    print("   • Copy the chat ID shown in the bot's response")
    print("   • Add to .env file: TELEGRAM_CHAT_ID=your_chat_id_here")
    
    print("\n3️⃣  TEST SETUP:")
    print("   • Run: python telegram_bot_manager.py test")
    print("   • Run: python telegram_bot_manager.py announce")
    
    print("\n📝 Current .env status:")
    if not existing_token or existing_token in ['your_telegram_bot_token_here', 'your_bot_token_here']:
        print("   ❌ TELEGRAM_BOT_TOKEN needs to be set")
    else:
        print("   ✅ TELEGRAM_BOT_TOKEN is configured")
    
    if not existing_chat_id or existing_chat_id in ['your_chat_id_here', 'YOUR_CHAT_ID']:
        print("   ❌ TELEGRAM_CHAT_ID needs to be set")
    else:
        print("   ✅ TELEGRAM_CHAT_ID is configured")
    
    print("\n🚀 Ready to start? Run the appropriate command above!")
    
    # If token is set but chat ID isn't, suggest next step
    if (existing_token and existing_token not in ['your_telegram_bot_token_here', 'your_bot_token_here'] and
        (not existing_chat_id or existing_chat_id in ['your_chat_id_here', 'YOUR_CHAT_ID'])):
        print("\n💡 Next step: Run 'python telegram_bot_manager.py chat_id' to get your chat ID")


async def get_chat_id():
    """Helper to get chat ID by showing instructions for manual discovery."""
    print("🔍 Chat ID Discovery Guide")
    print("=" * 27)
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ No TELEGRAM_BOT_TOKEN found in environment variables")
        print("Please set your bot token in the .env file first")
        return
    
    if token in ['your_telegram_bot_token_here', 'your_bot_token_here', 'YOUR_BOT_TOKEN']:
        print("❌ TELEGRAM_BOT_TOKEN appears to be a placeholder")
        print("Please set your actual bot token from @BotFather in the .env file")
        return
    
    try:
        from cosypolyamory.telegram_bot import CosyPolyTelegramBot
        
        # Test bot connection first
        bot = CosyPolyTelegramBot(token=token, chat_id=None)
        await bot.initialize()
        
        bot_info = await bot.bot.get_me()
        print(f"✅ Bot connected: @{bot_info.username}")
        
        await bot.stop()
        
        print(f"\n📋 How to get your Chat ID:")
        print(f"=" * 30)
        print(f"1. Open Telegram and find your bot: @{bot_info.username}")
        print(f"2. Send /start to your bot")
        print(f"3. OR add your bot to a group chat")
        print(f"4. In a web browser, go to:")
        print(f"   https://api.telegram.org/bot{token}/getUpdates")
        print(f"5. Look for 'chat':{'id'} in the JSON response")
        print(f"6. Copy that number (it might be negative for groups)")
        print(f"7. Add to your .env file: TELEGRAM_CHAT_ID=your_chat_id_number")
        
        print(f"\n💡 Alternative method:")
        print(f"1. Forward any message from your chat to @userinfobot")
        print(f"2. It will show you the chat ID")
        
        print(f"\n🧪 After getting the chat ID:")
        print(f"1. Update your .env file")
        print(f"2. Run: python telegram_bot_manager.py test")
        print(f"3. Run: python telegram_bot_manager.py announce")
        
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_bot_connection():
    """Test bot connection and basic functionality."""
    print("🧪 Testing Bot Connection")
    print("=" * 25)
    
    # Check token first
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
        return False
    
    if token in ['your_telegram_bot_token_here', 'your_bot_token_here', 'YOUR_BOT_TOKEN']:
        print("❌ TELEGRAM_BOT_TOKEN appears to be a placeholder")
        print("Please set your actual bot token from @BotFather")
        return False
    
    bot = await create_bot_from_env()
    if not bot:
        print("❌ Failed to create bot. Check your bot token.")
        return False
    
    try:
        # Test bot info
        bot_info = await bot.bot.get_me()
        print(f"✅ Bot connected: @{bot_info.username}")
        print(f"   Name: {bot_info.first_name}")
        print(f"   ID: {bot_info.id}")
        
        # Test sending a message if chat ID is available and valid
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if bot.chat_id and chat_id not in ['your_chat_id_here', 'YOUR_CHAT_ID', '']:
            print(f"\n📤 Testing message sending to chat {bot.chat_id}...")
            success = await bot.send_announcement("🧪 Test message from setup script")
            if success:
                print(f"✅ Test message sent to chat {bot.chat_id}")
            else:
                print(f"❌ Failed to send test message to chat {bot.chat_id}")
        else:
            print("\n⚠️  No valid chat ID configured.")
            print("   Use 'python telegram_bot_manager.py chat_id' to discover your chat ID")
            print("   Then add TELEGRAM_CHAT_ID=your_chat_id to your .env file")
        
        await bot.stop()
        return True
        
    except Exception as e:
        print(f"❌ Error testing bot: {e}")
        return False


async def send_test_announcement():
    """Send a test announcement to verify everything works."""
    print("📢 Sending Test Announcement")
    print("=" * 30)
    
    # Check if chat ID is configured
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not chat_id or chat_id in ['your_chat_id_here', 'YOUR_CHAT_ID', '']:
        print("❌ No valid chat ID configured!")
        print("\n💡 To send announcements, you need to:")
        print("1. Run: python telegram_bot_manager.py chat_id")
        print("2. Send any message to your bot")
        print("3. Copy the chat ID to your .env file")
        print("4. Then try this command again")
        return
    
    message = input("Enter test message (or press Enter for default): ").strip()
    if not message:
        message = "🧪 This is a test announcement from the Cosy Polyamory bot setup!"
    
    bot = await create_bot_from_env()
    if not bot:
        print("❌ Failed to create bot. Check your environment variables.")
        return
    
    try:
        success = await bot.send_announcement(message)
        if success:
            print("✅ Test announcement sent successfully!")
        else:
            print("❌ Failed to send test announcement")
    finally:
        await bot.stop()


async def send_test_event():
    """Send a test event notification."""
    print("🎉 Sending Test Event Notification")
    print("=" * 35)
    
    # Check if chat ID is configured
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not chat_id or chat_id in ['your_chat_id_here', 'YOUR_CHAT_ID', '']:
        print("❌ No valid chat ID configured!")
        print("\n💡 To send event notifications, you need to:")
        print("1. Run: python telegram_bot_manager.py chat_id")
        print("2. Send any message to your bot")
        print("3. Copy the chat ID to your .env file")
        print("4. Then try this command again")
        return
    
    bot = await create_bot_from_env()
    if not bot:
        print("❌ Failed to create bot. Check your environment variables.")
        return
    
    try:
        success = await bot.send_event_notification(
            event_title="Test Community Gathering",
            event_date="September 15, 2025",
            event_time="7:00 PM PST",
            event_location="Community Center - Main Hall",
            event_url="https://cosypolyamory.org/events/test"
        )
        
        if success:
            print("✅ Test event notification sent successfully!")
        else:
            print("❌ Failed to send test event notification")
    finally:
        await bot.stop()


async def run_bot_server():
    """Run the bot in server mode (polling for messages)."""
    print("🚀 Starting Telegram Bot Server")
    print("=" * 32)
    print("Press Ctrl+C to stop")
    
    bot = await create_bot_from_env()
    if not bot:
        print("❌ Failed to create bot. Check your environment variables.")
        return
    
    try:
        await bot.start_polling()
    except KeyboardInterrupt:
        print("\n⏹️  Stopping bot...")
        await bot.stop()
        print("✅ Bot stopped successfully")


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="Cosy Polyamory Telegram Bot Management")
    parser.add_argument('command', choices=[
        'setup', 'test', 'chat_id', 'announce', 'event', 'run'
    ], help='Command to execute')
    
    # Add help text for each command
    if len(sys.argv) == 1:
        print("🤖 Cosy Polyamory Telegram Bot Manager")
        print("=" * 38)
        print("\nAvailable commands:")
        print("  setup     - Interactive setup guide")
        print("  test      - Test bot connection")
        print("  chat_id   - Discover chat ID (run bot to get chat ID)")
        print("  announce  - Send test announcement")
        print("  event     - Send test event notification")
        print("  run       - Run bot in polling mode")
        print("\n💡 Start with: python telegram_bot_manager.py setup")
        return
    
    args = parser.parse_args()
    
    if args.command == 'setup':
        asyncio.run(setup_bot_interactive())
    elif args.command == 'test':
        asyncio.run(test_bot_connection())
    elif args.command == 'chat_id':
        asyncio.run(get_chat_id())
    elif args.command == 'announce':
        asyncio.run(send_test_announcement())
    elif args.command == 'event':
        asyncio.run(send_test_event())
    elif args.command == 'run':
        asyncio.run(run_bot_server())


if __name__ == "__main__":
    main()
