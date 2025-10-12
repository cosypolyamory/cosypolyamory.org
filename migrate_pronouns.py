#!/usr/bin/env python3
"""
Database migration script to consolidate pronoun fields.

This script:
1. Combines pronoun_singular and pronoun_plural into a single "pronouns" field
2. Renames pronoun_singular column to pronouns  
3. Drops the pronoun_plural column

Usage: python migrate_pronouns.py
"""

import os
import sys
from cosypolyamory.database import database
from cosypolyamory.models.user import User

def migrate_pronouns():
    """Migrate pronoun fields from separate singular/plural to combined pronouns field"""
    
    print("🔄 Starting pronoun migration...")
    
    try:
        # Connect to database
        database.connect()
        print("✅ Connected to database")
        
        # First, let's see what we're working with
        # Query directly from database since model might not match current schema
        try:
            users_with_pronouns_data = database.execute_sql(
                "SELECT id, name, pronoun_singular, pronoun_plural FROM users WHERE pronoun_singular IS NOT NULL OR pronoun_plural IS NOT NULL"
            ).fetchall()
            pronoun_users = len(users_with_pronouns_data)
        except Exception as e:
            print(f"ℹ️ Could not query old pronoun fields (expected if already migrated): {e}")
            users_with_pronouns_data = []
            pronoun_users = 0
        
        total_users = User.select().count()
        print(f"📊 Total users: {total_users}")
        print(f"📊 Users with pronouns: {pronoun_users}")
        
        if pronoun_users == 0:
            print("ℹ️ No users have pronouns set. Proceeding with schema changes only.")
        
        # Step 1: Add new 'pronouns' column (temporarily)
        print("\n📝 Step 1: Adding temporary 'pronouns' column...")
        try:
            database.execute_sql('ALTER TABLE users ADD COLUMN pronouns VARCHAR(255)')
            print("✅ Added 'pronouns' column")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("ℹ️ 'pronouns' column already exists, continuing...")
            else:
                raise e
        
        # Step 2: Migrate data by combining singular and plural
        print("\n📝 Step 2: Migrating pronoun data...")
        updated_count = 0
        
        for user_data in users_with_pronouns_data:
            user_id, name, pronoun_singular, pronoun_plural = user_data
            combined_pronouns = ""
            
            if pronoun_singular and pronoun_plural:
                # Combine both: "they/them", "she/her", "he/him"
                combined_pronouns = f"{pronoun_singular}/{pronoun_plural}"
            elif pronoun_singular:
                # Only singular available
                combined_pronouns = pronoun_singular
            elif pronoun_plural:
                # Only plural available (edge case)
                combined_pronouns = pronoun_plural
            
            if combined_pronouns:
                # Update the new pronouns field using raw SQL
                database.execute_sql(
                    "UPDATE users SET pronouns = ? WHERE id = ?",
                    (combined_pronouns, user_id)
                )
                updated_count += 1
                print(f"  ✅ Updated {name}: '{combined_pronouns}'")
        
        print(f"📊 Updated {updated_count} users with combined pronouns")
        
        # Step 3: Drop the old columns
        print("\n📝 Step 3: Dropping old pronoun columns...")
        
        try:
            database.execute_sql('ALTER TABLE users DROP COLUMN pronoun_singular')
            print("✅ Dropped 'pronoun_singular' column")
        except Exception as e:
            print(f"⚠️ Could not drop pronoun_singular: {e}")
        
        try:
            database.execute_sql('ALTER TABLE users DROP COLUMN pronoun_plural')
            print("✅ Dropped 'pronoun_plural' column")
        except Exception as e:
            print(f"⚠️ Could not drop pronoun_plural: {e}")
        
        # Step 4: Verify the migration
        print("\n📝 Step 4: Verifying migration...")
        
        # Check that the new column exists and has data
        users_with_new_pronouns = database.execute_sql(
            "SELECT COUNT(*) FROM users WHERE pronouns IS NOT NULL AND pronouns != ''"
        ).fetchone()[0]
        
        print(f"📊 Users with pronouns after migration: {users_with_new_pronouns}")
        
        if users_with_new_pronouns == updated_count:
            print("✅ Migration verification successful!")
        else:
            print(f"⚠️ Migration count mismatch: expected {updated_count}, found {users_with_new_pronouns}")
        
        # Show some examples
        sample_users = database.execute_sql(
            "SELECT name, pronouns FROM users WHERE pronouns IS NOT NULL LIMIT 5"
        ).fetchall()
        
        if sample_users:
            print("\n📋 Sample migrated data:")
            for name, pronouns in sample_users:
                print(f"  • {name}: {pronouns}")
        
        print("\n🎉 Pronoun migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if not database.is_closed():
            database.close()
            print("📝 Database connection closed")
    
    return True

def rollback_migration():
    """Rollback the migration by recreating the old columns"""
    print("🔄 Rolling back pronoun migration...")
    
    try:
        database.connect()
        print("✅ Connected to database")
        
        # Add back the old columns
        try:
            database.execute_sql('ALTER TABLE users ADD COLUMN pronoun_singular VARCHAR(255)')
            print("✅ Re-added 'pronoun_singular' column")
        except Exception as e:
            print(f"ℹ️ pronoun_singular already exists: {e}")
        
        try:
            database.execute_sql('ALTER TABLE users ADD COLUMN pronoun_plural VARCHAR(255)')
            print("✅ Re-added 'pronoun_plural' column") 
        except Exception as e:
            print(f"ℹ️ pronoun_plural already exists: {e}")
        
        # Split the combined pronouns back
        users_with_pronouns = database.execute_sql(
            "SELECT id, pronouns FROM users WHERE pronouns IS NOT NULL AND pronouns != ''"
        ).fetchall()
        
        updated_count = 0
        for user_id, pronouns in users_with_pronouns:
            if '/' in pronouns:
                parts = pronouns.split('/', 1)
                singular = parts[0].strip()
                plural = parts[1].strip()
            else:
                singular = pronouns.strip()
                plural = None
            
            User.update(
                pronoun_singular=singular,
                pronoun_plural=plural
            ).where(User.id == user_id).execute()
            updated_count += 1
        
        print(f"📊 Rolled back {updated_count} users")
        print("🎉 Rollback completed!")
        
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False
    
    finally:
        if not database.is_closed():
            database.close()
    
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    else:
        print("Pronoun Migration Script")
        print("======================")
        print()
        print("This will combine pronoun_singular and pronoun_plural into a single 'pronouns' field.")
        print("Examples: 'they' + 'them' → 'they/them', 'she' + 'her' → 'she/her'")
        print()
        
        confirm = input("Continue with migration? (y/N): ").strip().lower()
        if confirm in ['y', 'yes']:
            success = migrate_pronouns()
            if not success:
                print("\n❌ Migration failed. You can try running the rollback with:")
                print("python migrate_pronouns.py rollback")
        else:
            print("Migration cancelled.")