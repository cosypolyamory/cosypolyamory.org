#!/usr/bin/env python3
"""
Script to add "Deleted User" system account to existing databases.
This script should be run after updating the codebase to ensure
the system account exists for event reassignment during user deletion.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cosypolyamory.database import database
from cosypolyamory.models.user import User

def add_deleted_user():
    """Add the 'Deleted User' system account to the database"""
    
    try:
        # Connect to database
        database.connect()
        print("✅ Connected to database")
        
        # Check if deleted user already exists
        try:
            existing_user = User.get(User.id == 'system_deleted_user')
            print(f"✅ 'Deleted User' already exists: {existing_user.name} ({existing_user.email})")
            return True
            
        except User.DoesNotExist:
            # Create the deleted user
            deleted_user = User.create(
                id='system_deleted_user',
                email='deleted@system.local',
                name='Deleted User',
                avatar_url='',
                provider='system',
                role='deleted',
                is_approved=True,
                pronouns=None
            )
            
            print(f"✅ Created 'Deleted User': {deleted_user.name} ({deleted_user.email})")
            print("   This account will be used to preserve events when users are deleted.")
            return True
            
    except Exception as e:
        print(f"❌ Error adding deleted user: {e}")
        return False
        
    finally:
        if database.is_closed() is False:
            database.close()
            print("✅ Database connection closed")

def main():
    """Main function"""
    print("🔧 Adding 'Deleted User' system account to database...")
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Check if DATABASE_PATH is set
    if not os.getenv('DATABASE_PATH'):
        print("❌ DATABASE_PATH environment variable not set")
        print("💡 Please set DATABASE_PATH in your .env file or environment variables")
        sys.exit(1)
    
    db_path = os.getenv('DATABASE_PATH')
    print(f"🗄️  Database path: {os.path.abspath(db_path)}")
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"❌ Database file does not exist: {db_path}")
        print("💡 Initialize the database first using the normal startup process")
        sys.exit(1)
    
    # Add the deleted user
    success = add_deleted_user()
    
    if success:
        print("\n✅ Successfully added 'Deleted User' system account")
        print("🎉 Your database is ready for the new user deletion behavior")
    else:
        print("\n❌ Failed to add 'Deleted User' system account")
        sys.exit(1)

if __name__ == '__main__':
    main()