#!/usr/bin/env python3
"""
Migration script to update Event schema with new fields:
- postcode_area -> barrio
- full_address -> establishment_name + google_maps_link
- requirements -> tips_for_attendees
"""

import sqlite3
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database path from environment
DATABASE_PATH = os.getenv('DATABASE_PATH', 'cosypolyamory.db')

def migrate_events_schema():
    """Migrate the events table to the new schema"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        print("🔄 Starting events schema migration...")
        
        # Check if the old schema exists
        cursor.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        # Check if migration is needed
        if 'barrio' in columns:
            print("✅ Schema already migrated!")
            return
        
        # Create backup table
        print("📦 Creating backup of existing events...")
        cursor.execute("""
            CREATE TABLE events_backup AS 
            SELECT * FROM events
        """)
        
        # Drop the old events table
        print("🗑️ Dropping old events table...")
        cursor.execute("DROP TABLE events")
        
        # Create new events table with updated schema
        print("🏗️ Creating new events table...")
        cursor.execute("""
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                barrio VARCHAR(255) NOT NULL,
                time_period VARCHAR(255) NOT NULL,
                date DATETIME NOT NULL,
                establishment_name VARCHAR(255) NOT NULL DEFAULT '',
                google_maps_link TEXT NOT NULL DEFAULT '',
                location_notes TEXT,
                exact_time DATETIME NOT NULL,
                end_time DATETIME,
                organizer_id VARCHAR(255) NOT NULL,
                co_host_id VARCHAR(255),
                max_attendees INTEGER,
                tips_for_attendees TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                requires_approval BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (organizer_id) REFERENCES users (id),
                FOREIGN KEY (co_host_id) REFERENCES users (id)
            )
        """)
        
        # Migrate data from backup
        print("📥 Migrating existing event data...")
        cursor.execute("""
            INSERT INTO events (
                id, title, description, barrio, time_period, date,
                establishment_name, google_maps_link, exact_time, end_time,
                organizer_id, co_host_id, max_attendees, tips_for_attendees,
                is_active, requires_approval, created_at, updated_at
            )
            SELECT 
                id, title, description, 
                COALESCE(postcode_area, 'Unknown Area') as barrio,
                time_period, date,
                'Please update establishment name' as establishment_name,
                'https://maps.google.com/' as google_maps_link,
                exact_time, end_time,
                organizer_id, co_host_id, max_attendees,
                NULL as tips_for_attendees,
                is_active, requires_approval, created_at, updated_at
            FROM events_backup
        """)
        
        # Drop the backup table
        cursor.execute("DROP TABLE events_backup")
        
        conn.commit()
        print("✅ Migration completed successfully!")
        
        # Show updated events
        cursor.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        print(f"📊 Migrated {count} events to new schema")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        print("🔄 Rolling back changes...")
        
        # Try to restore from backup if it exists
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_backup'")
            if cursor.fetchone():
                cursor.execute("DROP TABLE events")
                cursor.execute("ALTER TABLE events_backup RENAME TO events")
                conn.commit()
                print("✅ Rollback successful")
        except:
            print("❌ Rollback failed - manual intervention required")
        
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_events_schema()
