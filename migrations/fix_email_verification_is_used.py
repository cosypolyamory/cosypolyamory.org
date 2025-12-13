#!/usr/bin/env python3
"""
Migration: Fix is_used field type in email_verifications table

This migration fixes the is_used field from VARCHAR to BOOLEAN.
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cosypolyamory.database import database

def run_migration():
    """Fix the is_used field type"""
    print("🔧 Fixing email_verifications.is_used field type...")
    
    try:
        # Check current schema
        cursor = database.execute_sql("PRAGMA table_info(email_verifications)")
        columns = cursor.fetchall()
        
        print("Current schema:")
        for col in columns:
            print(f"  {col[1]}: {col[2]}")
        
        # Create new table with correct schema
        print("\n📝 Creating temporary table with correct schema...")
        database.execute_sql("""
            CREATE TABLE email_verifications_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                new_email VARCHAR(255) NOT NULL,
                token VARCHAR(255) NOT NULL UNIQUE,
                created_at DATETIME NOT NULL,
                expires_at DATETIME NOT NULL,
                verified_at DATETIME,
                is_used INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
            )
        """)
        
        # Copy data, converting VARCHAR 'False'/'True' to INTEGER 0/1
        print("📋 Copying data and converting is_used values...")
        database.execute_sql("""
            INSERT INTO email_verifications_new 
                (id, user_id, new_email, token, created_at, expires_at, verified_at, is_used)
            SELECT 
                id, 
                user_id, 
                new_email, 
                token, 
                created_at, 
                expires_at, 
                verified_at,
                CASE 
                    WHEN is_used = 'False' OR is_used = '0' OR is_used = '' THEN 0
                    ELSE 1
                END
            FROM email_verifications
        """)
        
        # Drop old table
        print("🗑️  Dropping old table...")
        database.execute_sql("DROP TABLE email_verifications")
        
        # Rename new table
        print("✨ Renaming new table...")
        database.execute_sql("ALTER TABLE email_verifications_new RENAME TO email_verifications")
        
        # Recreate index
        print("📇 Creating index on token...")
        database.execute_sql("CREATE UNIQUE INDEX email_verifications_token ON email_verifications(token)")
        
        print("\n✅ Migration completed successfully!")
        
        # Show final schema
        cursor = database.execute_sql("PRAGMA table_info(email_verifications)")
        columns = cursor.fetchall()
        print("\nNew schema:")
        for col in columns:
            print(f"  {col[1]}: {col[2]}")
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    run_migration()
