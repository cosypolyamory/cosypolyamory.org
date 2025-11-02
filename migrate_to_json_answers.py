#!/usr/bin/env python3
"""
Migration script to convert hardcoded question fields to JSON array
Migrates from question_1_answer, question_2_answer, etc. to a single JSON answers field
"""

import json
import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, '/home/robert/projects/cosypolyamory.org')

from cosypolyamory.database import database

def migrate_to_json_answers():
    """Migrate existing question_X_answer fields to JSON answers array"""
    
    print(f"🔄 Starting migration to JSON answers format...")
    print(f"📅 Migration started at: {datetime.now()}")
    
    try:
        # Connect to database
        database.connect()
        
        # Check current table structure
        cursor = database.execute_sql("PRAGMA table_info(user_applications)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        print(f"📋 Current columns: {list(columns.keys())}")
        
        # Add answers column if it doesn't exist
        if 'answers' not in columns:
            print("➕ Adding 'answers' column...")
            database.execute_sql("ALTER TABLE user_applications ADD COLUMN answers TEXT")
        else:
            print("✅ 'answers' column already exists")
        
        # Get all applications that need migration
        cursor = database.execute_sql("""
            SELECT id, question_1_answer, question_2_answer, question_3_answer, 
                   question_4_answer, question_5_answer, question_6_answer, question_7_answer
            FROM user_applications 
            WHERE answers IS NULL
        """)
        
        applications = cursor.fetchall()
        print(f"📋 Found {len(applications)} applications to migrate")
        
        # Get current questions from environment
        questions = {}
        for i in range(1, 8):
            question = os.getenv(f'QUESTION_{i}')
            if question:
                questions[f'question_{i}'] = question
        
        print(f"📝 Using {len(questions)} questions from environment")
        
        migrated_count = 0
        
        for app_row in applications:
            app_id = app_row[0]
            # Collect existing answers (skip the id field)
            old_answers = app_row[1:]
            
            # Only migrate if there are non-empty answers
            if any(answer and answer.strip() for answer in old_answers if answer is not None):
                # Create questions and answers dictionary
                qa_data = {}
                for i, answer in enumerate(old_answers, 1):
                    question_key = f'question_{i}'
                    if question_key in questions:
                        qa_data[question_key] = {
                            'question': questions[question_key],
                            'answer': answer if answer is not None else ""
                        }
                
                json_answers = json.dumps(qa_data)
                database.execute_sql(
                    "UPDATE user_applications SET answers = ? WHERE id = ?",
                    (json_answers, app_id)
                )
                migrated_count += 1
                print(f"✅ Migrated application {app_id}")
            else:
                print(f"⏭️  Skipped application {app_id} (no answers)")
        
        print(f"\n🎉 Migration completed! Migrated {migrated_count} applications")
        
        # Test the new structure
        print("\n🧪 Testing new structure...")
        test_cursor = database.execute_sql(
            "SELECT id, answers FROM user_applications WHERE answers IS NOT NULL LIMIT 3"
        )
        test_rows = test_cursor.fetchall()
        
        for row in test_rows:
            app_id, answers_json = row
            try:
                qa_data = json.loads(answers_json) if answers_json else {}
                if isinstance(qa_data, dict) and qa_data:
                    first_key = next(iter(qa_data.keys()))
                    first_value = qa_data[first_key]
                    if isinstance(first_value, dict) and 'question' in first_value:
                        print(f"   App {app_id}: {len(qa_data)} question/answer pairs (new format)")
                    else:
                        print(f"   App {app_id}: {len(qa_data)} answers (old format)")
                else:
                    print(f"   App {app_id}: No data")
            except json.JSONDecodeError as e:
                print(f"   ❌ App {app_id}: JSON decode error: {e}")
        
        print("\n📋 Migration summary:")
        print(f"   - Total applications processed: {len(applications)}")
        print(f"   - Successfully migrated: {migrated_count}")
        print(f"   - Skipped (no data): {len(applications) - migrated_count}")
        
        print("\n⚠️  Note: Old question columns are preserved for safety.")
        print("   After verifying everything works, you can drop them with:")
        for i in range(1, 8):
            print(f"   ALTER TABLE user_applications DROP COLUMN question_{i}_answer;")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if database and not database.is_closed():
            database.close()
    
    return True

if __name__ == "__main__":
    success = migrate_to_json_answers()
    sys.exit(0 if success else 1)