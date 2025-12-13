#!/usr/bin/env python3
"""
Simple test script for the Cosy Polyamory Telegram Bot.

This script tests basic bot functionality without requiring the full application setup.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cosypolyamory.telegram_bot import CosyPolyTelegramBot, create_bot_from_env


async def test_basic_functionality():
    """Test basic bot functionality."""
    print("🤖 Testing Cosy Polyamory Telegram Bot")
    print("=" * 40)
    
    # Check environment variables
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
        print("   Please add it to your .env file")
        return False
    
    if not chat_id:
        print("⚠️  TELEGRAM_CHAT_ID not found - will skip message sending tests")
    
    print(f"✅ Bot token found: {token[:10]}...")
    if chat_id:
        print(f"✅ Chat ID found: {chat_id}")
    
    # Test bot creation and initialization
    print("\n🔧 Testing bot initialization...")
    try:
        bot = await create_bot_from_env()
        if not bot:
            print("❌ Failed to create bot instance")
            return False
        
        print("✅ Bot created successfully")
        
        # Test getting bot info
        bot_info = await bot.bot.get_me()
        print(f"✅ Bot info retrieved: @{bot_info.username} ({bot_info.first_name})")
        
        # Test sending messages if chat ID is available
        if chat_id:
            print("\n📢 Testing message sending...")
            
            # Test basic announcement
            success = await bot.send_announcement("🧪 Test announcement from bot test script")
            if success:
                print("✅ Basic announcement sent successfully")
            else:
                print("❌ Failed to send basic announcement")
            
            # Test event notification
            success = await bot.send_event_notification(
                event_title="Test Event from Bot Script",
                event_date="September 15, 2025",
                event_time="7:00 PM PST",
                event_location="Test Location",
                event_url="https://example.com/test"
            )
            if success:
                print("✅ Event notification sent successfully")
            else:
                print("❌ Failed to send event notification")
            
            # Test event update
            success = await bot.send_event_update(
                event_title="Test Event from Bot Script",
                update_type="UPDATED",
                details="This is a test update message from the bot test script."
            )
            if success:
                print("✅ Event update sent successfully")
            else:
                print("❌ Failed to send event update")
        
        await bot.stop()
        print("\n✅ All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False


async def test_integration_functions():
    """Test the integration module functions."""
    print("\n🔗 Testing integration functions...")
    
    try:
        from cosypolyamory.telegram_integration import TelegramNotificationService
        
        service = TelegramNotificationService()
        
        if not service.enabled:
            print("⚠️  Telegram service not enabled (missing configuration)")
            return False
        
        # Test custom announcement
        success = await service.send_custom_announcement("🧪 Test from integration service")
        if success:
            print("✅ Integration service announcement sent successfully")
        else:
            print("❌ Failed to send integration service announcement")
        
        return success
        
    except Exception as e:
        print(f"❌ Error testing integration functions: {e}")
        return False


def check_dependencies():
    """Check if required dependencies are installed."""
    print("📦 Checking dependencies...")
    
    try:
        import telegram
        print("✅ python-telegram-bot is installed")
        return True
    except ImportError:
        print("❌ python-telegram-bot is not installed")
        print("   Run: pip install python-telegram-bot")
        return False


async def main():
    """Main test function."""
    print("🧪 Cosy Polyamory Telegram Bot Test Suite")
    print("=" * 45)
    
    # Check dependencies
    if not check_dependencies():
        return
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run basic functionality tests
    basic_success = await test_basic_functionality()
    
    # Run integration tests
    integration_success = await test_integration_functions()
    
    # Summary
    print("\n" + "=" * 45)
    print("📊 Test Results Summary:")
    print(f"   Basic functionality: {'✅ PASS' if basic_success else '❌ FAIL'}")
    print(f"   Integration functions: {'✅ PASS' if integration_success else '❌ FAIL'}")
    
    if basic_success and integration_success:
        print("\n🎉 All tests passed! Your Telegram bot is ready to use.")
    else:
        print("\n⚠️  Some tests failed. Check the configuration and try again.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
