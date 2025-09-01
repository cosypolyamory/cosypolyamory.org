#!/usr/bin/env python3
"""
Database management script for Cosy Polyamory
"""

import sys
import argparse
from datetime import datetime

# Import database and models
from cosypolyamory.database import init_database, get_database
from cosypolyamory.models.user import User

def init_database_cmd():
    """Initialize database and create tables"""
    init_database()

def list_users():
    """List all users"""
    database = get_database()
    database.connect()
    users = User.select()
    if users:
        print("\n📋 Current Users:")
        print("-" * 80)
        print(f"{'ID':<25} {'Name':<20} {'Email':<30} {'Provider':<10} {'Admin'}")
        print("-" * 80)
        for user in users:
            admin_status = "✅" if user.is_admin else "❌"
            print(f"{user.id:<25} {user.name:<20} {user.email:<30} {user.provider:<10} {admin_status}")
    else:
        print("No users found in database")
    database.close()

def make_admin(email):
    """Make a user admin by email"""
    database = get_database()
    database.connect()
    try:
        user = User.get(User.email == email)
        user.is_admin = True
        user.role = 'admin'
        user.save()
        print(f"✅ User {email} is now an admin (role set to 'admin')")
    except User.DoesNotExist:
        print(f"❌ User with email {email} not found")
    database.close()

def remove_admin(email):
    """Remove admin status from a user"""
    database = get_database()
    database.connect()
    try:
        user = User.get(User.email == email)
        user.is_admin = False
        # Set role to 'approved' if user was admin, otherwise leave as is
        if user.role == 'admin':
            user.role = 'approved'
        user.save()
        print(f"✅ Admin status removed from {email} (role set to '{user.role}')")
    except User.DoesNotExist:
        print(f"❌ User with email {email} not found")
    database.close()

def main():
    parser = argparse.ArgumentParser(description='Manage Cosy Polyamory database')
    parser.add_argument('command', choices=['init', 'list', 'make-admin', 'remove-admin', 'migrate'], 
                       help='Command to execute')
    parser.add_argument('email', nargs='?', help='User email for admin operations')
    
    args = parser.parse_args()
    
    if args.command == 'init':
        init_database_cmd()
    elif args.command == 'list':
        list_users()
    elif args.command == 'make-admin':
        if not args.email:
            print("❌ Email required for make-admin command")
            print("Usage: python manage_db.py make-admin <email>")
            sys.exit(1)
        make_admin(args.email)
    elif args.command == 'remove-admin':
        if not args.email:
            print("❌ Email required for remove-admin command")
            print("Usage: python manage_db.py remove-admin <email>")
            sys.exit(1)
        remove_admin(args.email)

if __name__ == '__main__':
    main()
