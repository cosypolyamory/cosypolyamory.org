"""
Database configuration and initialization
"""

import os
from peewee import SqliteDatabase
from dotenv import load_dotenv

# Load environment variables from current directory only
# This prevents loading .env files from parent directories
dotenv_path = os.path.join(os.getcwd(), '.env')
load_dotenv(dotenv_path=dotenv_path)

# Database configuration - require explicit DATABASE_PATH
DATABASE_PATH = os.getenv('DATABASE_PATH')
if not DATABASE_PATH:
    print("❌ DATABASE_PATH environment variable is not set!")
    print("💡 Please set DATABASE_PATH in your .env file or environment variables")
    print("   Example: DATABASE_PATH=cosypolyamory.db")
    print(f"   Current working directory: {os.getcwd()}")
    print(f"   Looked for .env file in: {os.path.join(os.getcwd(), '.env')}")
    import sys
    sys.exit(1)

database = SqliteDatabase(DATABASE_PATH)

def init_database():
    """Initialize database and create all tables"""
    import sys
    from cosypolyamory.models.user import User
    from cosypolyamory.models.user_application import UserApplication
    from cosypolyamory.models.event import Event
    from cosypolyamory.models.rsvp import RSVP
    from cosypolyamory.models.event_note import EventNote
    from cosypolyamory.models.no_show import NoShow
    
    # Get absolute path for logging
    abs_db_path = os.path.abspath(DATABASE_PATH)
    print(f"🗄️  Opening database: {abs_db_path}")
    
    # Check database directory permissions
    db_dir = os.path.dirname(abs_db_path)
    if not db_dir:  # If no directory specified, use current directory
        db_dir = os.getcwd()
        
    if not os.path.exists(db_dir):
        print(f"❌ Database directory does not exist: {db_dir}")
        print("💡 Create the directory or specify a valid DATABASE_PATH")
        sys.exit(1)
        
    if not os.access(db_dir, os.W_OK):
        print(f"❌ Database directory is not writable: {db_dir}")
        print("💡 Check directory permissions or run with appropriate privileges")
        sys.exit(1)
    
    # If database file exists, check if it's writable
    if os.path.exists(abs_db_path):
        if not os.access(abs_db_path, os.W_OK):
            print(f"❌ Database file is not writable: {abs_db_path}")
            print("💡 Check file permissions or run with appropriate privileges")
            sys.exit(1)
        print(f"📊 Database file exists ({os.path.getsize(abs_db_path)} bytes)")
    else:
        print(f"🔧 Database file will be created: {abs_db_path}")
    
    try:
        database.connect()
        database.create_tables([User, UserApplication, Event, RSVP, EventNote, NoShow], safe=True)
        
        # Create a "Deleted User" placeholder if it doesn't exist
        deleted_user, created = User.get_or_create(
            email='deleted@system.local',
            defaults={
                'id': 'system_deleted_user',
                'name': 'Deleted User',
                'avatar_url': '',
                'provider': 'system',
                'role': 'deleted'
            }
        )
        
        if created:
            print("✅ Created 'Deleted User' system placeholder")
        
        print(f"✅ Database initialized successfully: {abs_db_path}")
        database.close()
        
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        print(f"💡 Check database path and permissions: {abs_db_path}")
        sys.exit(1)

def get_database():
    """Get database instance"""
    return database
