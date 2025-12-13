#!/usr/bin/env python3
"""
Migration script to add 'published' field to existing events.
This script should be run after updating the Event model to include the 'published' field.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cosypolyamory.database import database
from cosypolyamory.models.event import Event

def add_published_field():
    """Add the 'published' field to the Event table and set existing events as published"""
    
    try:
        # Connect to database
        database.connect()
        print("✅ Connected to database")
        
        # Add the published column to the table
        try:
            # Check if column already exists
            cursor = database.cursor()
            cursor.execute("PRAGMA table_info(events)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'published' not in columns:
                # Add the published column with default value False
                cursor.execute("ALTER TABLE events ADD COLUMN published BOOLEAN DEFAULT 0")
                print("✅ Added 'published' column to events table")
                
                # Set all existing events as published (so they remain visible)
                Event.update(published=True).execute()
                print("✅ Set all existing events as published")
                
            else:
                print("✅ 'published' column already exists")
                
                # Check how many events are published vs unpublished
                published_count = Event.select().where(Event.published == True).count()
                unpublished_count = Event.select().where(Event.published == False).count()
                total_count = Event.select().count()
                
                print(f"📊 Event status summary:")
                print(f"   - Published events: {published_count}")
                print(f"   - Unpublished events: {unpublished_count}")
                print(f"   - Total events: {total_count}")
            
        except Exception as e:
            print(f"❌ Error adding column: {e}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error in migration: {e}")
        return False
        
    finally:
        if database.is_closed() is False:
            database.close()
            print("✅ Database connection closed")

def main():
    """Main function"""
    print("🔄 Adding 'published' field to events table...")
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
    
    # Run the migration
    success = add_published_field()
    
    if success:
        print("\n✅ Successfully added 'published' field to events table")
        print("🎉 Events can now be saved as drafts!")
    else:
        print("\n❌ Failed to add 'published' field")
        sys.exit(1)

if __name__ == '__main__':
    main()