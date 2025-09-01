#!/usr/bin/env python3
"""
Migration script to add no_show_count field to users table

This script safely adds the no_show_count IntegerField to the User model
for existing databases. It can be run on production/test servers.

Usage:
    python migrate_add_no_show_count.py
"""

import os
import sys
from datetime import datetime

def run_migration():
    """Run the migration to add no_show_count field"""
    
    # Import database and models
    try:
        from cosypolyamory.database import get_database
        from cosypolyamory.models.user import User
    except ImportError as e:
        print(f"❌ Failed to import modules: {e}")
        print("💡 Make sure you're running from the project root directory")
        sys.exit(1)
    
    database = get_database()
    
    print("🔄 Starting migration: Add no_show_count field to users table")
    print(f"📅 Migration date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🗄️  Database: {database.database}")
    
    try:
        database.connect()
        
        # Check if the column already exists
        cursor = database.execute_sql("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'no_show_count' in columns:
            print("✅ Column 'no_show_count' already exists in users table")
            print("🔍 Checking current values...")
            
            # Show some stats about existing values
            result = database.execute_sql("SELECT COUNT(*) as total, SUM(no_show_count) as total_no_shows FROM users")
            total_users, total_no_shows = result.fetchone()
            print(f"📊 Total users: {total_users}")
            print(f"📊 Total no-shows recorded: {total_no_shows or 0}")
            
        else:
            print("🔧 Adding 'no_show_count' column to users table...")
            
            # Add the column with default value
            database.execute_sql("ALTER TABLE users ADD COLUMN no_show_count INTEGER DEFAULT 0")
            
            # Update any NULL values to 0 (shouldn't be needed with DEFAULT, but just in case)
            database.execute_sql("UPDATE users SET no_show_count = 0 WHERE no_show_count IS NULL")
            
            print("✅ Successfully added 'no_show_count' column")
            
            # Verify the column was added
            cursor = database.execute_sql("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'no_show_count' in columns:
                print("✅ Column addition verified")
                
                # Show user count
                result = database.execute_sql("SELECT COUNT(*) FROM users")
                user_count = result.fetchone()[0]
                print(f"📊 Updated {user_count} user records with default no_show_count = 0")
            else:
                print("❌ Column addition failed - column not found after migration")
                sys.exit(1)
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print("💡 Please check database permissions and try again")
        sys.exit(1)
    
    finally:
        if database and not database.is_closed():
            database.close()
    
    print("🎉 Migration completed successfully!")
    print("💡 The User model now supports tracking no-show counts for events")

def main():
    """Main function"""
    print("=" * 60)
    print("   COSY POLYAMORY DATABASE MIGRATION")
    print("   Add no_show_count field to User model")
    print("=" * 60)
    print()
    
    # Check if we're in the right directory
    if not os.path.exists('cosypolyamory') or not os.path.exists('manage_db.py'):
        print("❌ Please run this script from the project root directory")
        print("💡 You should see 'cosypolyamory/' folder and 'manage_db.py' in the current directory")
        sys.exit(1)
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found")
        print("💡 Make sure you have a .env file with DATABASE_PATH configured")
        sys.exit(1)
    
    # Confirm before running
    response = input("🤔 Do you want to run this migration? [y/N]: ").strip().lower()
    if response not in ['y', 'yes']:
        print("❌ Migration cancelled by user")
        sys.exit(0)
    
    run_migration()

if __name__ == '__main__':
    main()
