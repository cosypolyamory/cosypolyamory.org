"""
Database configuration and initialization
"""

import os
from peewee import SqliteDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'cosypolyamory.db')
database = SqliteDatabase(DATABASE_PATH)

def init_database():
    """Initialize database and create all tables"""
    from cosypolyamory.models.user import User
    from cosypolyamory.models.user_application import UserApplication
    from cosypolyamory.models.event import Event
    from cosypolyamory.models.rsvp import RSVP
    
    database.connect()
    database.create_tables([User, UserApplication, Event, RSVP], safe=True)
    
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
    
    print(f"✅ Database initialized: {DATABASE_PATH}")
    database.close()

def get_database():
    """Get database instance"""
    return database
