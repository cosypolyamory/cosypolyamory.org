"""
User application model for the approval process
"""

import json
import os
from datetime import datetime
from peewee import CharField, TextField, DateTimeField, BooleanField, ForeignKeyField
from cosypolyamory.models import BaseModel
from cosypolyamory.models.user import User

class UserApplication(BaseModel):
    """User application for community approval"""
    user = ForeignKeyField(User, backref='application')
    
    # Store all questionnaire responses as JSON array
    answers = TextField(null=True)  # JSON array of answers
    
    submitted_at = DateTimeField(default=datetime.now)
    reviewed_at = DateTimeField(null=True)
    reviewed_by = ForeignKeyField(User, null=True, backref='reviewed_applications')
    review_notes = TextField(null=True)
    
    class Meta:
        table_name = 'user_applications'
    
    @property
    def status(self):
        """Derive status from user role"""
        if self.user.role == 'approved':
            return 'approved'
        elif self.user.role == 'rejected':
            return 'rejected'
        else:
            return 'pending'
    
    @staticmethod
    def get_questions_from_env():
        """Get all questions from environment variables as a dictionary"""
        questions = {}
        i = 1
        while True:
            question = os.getenv(f'QUESTION_{i}')
            if question is None:
                break
            questions[f'question_{i}'] = question
            i += 1
        return questions
    
    @staticmethod
    def get_question_count():
        """Get the number of questions from environment"""
        return len(UserApplication.get_questions_from_env())
    
    def get_answers(self):
        """Get answers as a dictionary of question_key -> answer"""
        if self.answers:
            try:
                stored_data = json.loads(self.answers)
                # Handle both old format (list) and new format (dict with questions+answers)
                if isinstance(stored_data, list):
                    # Old format: convert to question_key -> answer mapping
                    questions = self.get_questions_from_env()
                    result = {}
                    for i, answer in enumerate(stored_data):
                        if i < len(questions):
                            question_key = list(questions.keys())[i]
                            result[question_key] = answer
                    return result
                elif isinstance(stored_data, dict):
                    # New format: extract answers from question/answer pairs
                    if stored_data and 'question' in next(iter(stored_data.values()), {}):
                        # Format: {"question_1": {"question": "...", "answer": "..."}}
                        return {k: v.get('answer', '') for k, v in stored_data.items()}
                    else:
                        # Simple format: {"question_1": "answer"}
                        return stored_data
                return {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def get_questions_and_answers(self):
        """Get stored questions and answers as dictionary"""
        if self.answers:
            try:
                stored_data = json.loads(self.answers)
                # Handle both old format (list) and new format (dict with questions+answers)
                if isinstance(stored_data, list):
                    # Old format: use .env questions with stored answers
                    questions = self.get_questions_from_env()
                    result = {}
                    for i, answer in enumerate(stored_data):
                        if i < len(questions):
                            question_key = list(questions.keys())[i]
                            result[question_key] = {
                                'question': questions[question_key],
                                'answer': answer
                            }
                    return result
                elif isinstance(stored_data, dict):
                    # Check if it's the full format with questions and answers
                    first_value = next(iter(stored_data.values()), {})
                    if isinstance(first_value, dict) and 'question' in first_value:
                        # Format: {"question_1": {"question": "...", "answer": "..."}}
                        return stored_data
                    else:
                        # Simple format: {"question_1": "answer"} - need to get questions from env
                        questions = self.get_questions_from_env()
                        result = {}
                        for question_key, answer in stored_data.items():
                            result[question_key] = {
                                'question': questions.get(question_key, f'Question {question_key.split("_")[1]}'),
                                'answer': answer
                            }
                        return result
                return {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def set_answers(self, answers_dict):
        """Set answers from a dictionary (question_key -> answer)"""
        self.answers = json.dumps(answers_dict) if answers_dict else None
    
    def set_questions_and_answers(self, qa_dict):
        """Set both questions and answers from dictionary"""
        # Format: {"question_1": {"question": "...", "answer": "..."}}
        self.answers = json.dumps(qa_dict) if qa_dict else None
    
    def get_answer(self, question_index):
        """Get a specific answer by index (0-based)"""
        answers = self.get_answers()
        question_keys = list(answers.keys())
        if 0 <= question_index < len(question_keys):
            return answers[question_keys[question_index]]
        return None
    
    def get_question_text(self, question_key):
        """Get the text of a specific question from stored data"""
        qa_data = self.get_questions_and_answers()
        return qa_data.get(question_key, {}).get('question', '')
    
    def __getattr__(self, name):
        """Dynamic attribute access for backward compatibility"""
        if name.startswith('question_') and name.endswith('_answer'):
            # Extract question number from attribute name like 'question_5_answer'
            try:
                question_num = int(name.split('_')[1])
                return self.get_answer(question_num - 1)  # Convert to 0-based index
            except (ValueError, IndexError):
                return None
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def __str__(self):
        return f"Application for {self.user.name} - {self.status}"
