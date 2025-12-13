#!/usr/bin/env python3
"""
Database migration: Add email_verifications table

This script adds the email_verifications table to the database for secure email changes.
Run this after updating the code to add email verification functionality.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cosypolyamory.database import database
from cosypolyamory.models.email_verification import EmailVerification


def migrate():
    """Add email_verifications table"""
    print("🔧 Starting database migration: Add email_verifications table")
    
    try:
        database.connect()
        
        # Check if table already exists
        if EmailVerification.table_exists():
            print("ℹ️  Table 'email_verifications' already exists. No migration needed.")
            database.close()
            return
        
        # Create the table
        database.create_tables([EmailVerification])
        print("✅ Successfully created 'email_verifications' table")
        
        database.close()
        print("✅ Migration completed successfully")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    migrate()
