#!/usr/bin/env python3
"""
Migration script: Remove no_show_count from User model and create NoShow table

This migration:
1. Creates the new NoShow table
2. Migrates existing no_show_count data to individual NoShow records (if any)
3. Removes the no_show_count column from User table

Note: Since we can't determine which specific events the old no_show_count
referred to, we'll just drop the old data and start fresh with the new system.
"""

import os
import sys

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from cosypolyamory.database import database
from cosypolyamory.models.user import User
from cosypolyamory.models.no_show import NoShow

def migrate_no_show_tracking():
    """Migration to implement new no-show tracking structure"""
    
    print("🔄 Starting no-show tracking migration...")
    
    try:
        database.connect()
        
        # Check if NoShow table already exists
        if database.table_exists('no_shows'):
            print("✅ NoShow table already exists, skipping creation")
        else:
            print("📝 Creating NoShow table...")
            database.create_tables([NoShow])
            print("✅ NoShow table created successfully")
        
        # Check if User table has no_show_count column
        cursor = database.execute_sql("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'no_show_count' in columns:
            print("🗑️  Removing no_show_count column from User table...")
            # Note: SQLite doesn't support DROP COLUMN directly
            # We would need to recreate the table, but since we're dropping
            # the old data anyway, we'll just leave the column and it will
            # be ignored in the new model
            print("ℹ️  Note: no_show_count column left in database but ignored by model")
            print("ℹ️  Previous no-show count data is not migrated (starting fresh)")
        else:
            print("✅ no_show_count column not found in User table")
        
        print("✅ Migration completed successfully!")
        print("📊 No-show tracking now uses individual records per event")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        if not database.is_closed():
            database.close()

if __name__ == "__main__":
    migrate_no_show_tracking()
