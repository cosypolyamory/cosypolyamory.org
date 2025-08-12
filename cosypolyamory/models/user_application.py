"""
User application model for the approval process
"""

from datetime import datetime
from peewee import CharField, TextField, DateTimeField, BooleanField, ForeignKeyField
from cosypolyamory.models import BaseModel
from cosypolyamory.models.user import User

class UserApplication(BaseModel):
    """User application for community approval"""
    user = ForeignKeyField(User, backref='application')
    status = CharField(choices=[
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='pending')
    
    # Questionnaire responses (stored as JSON-like text)
    question_1_answer = TextField(null=True)
    question_2_answer = TextField(null=True)
    question_3_answer = TextField(null=True)
    question_4_answer = TextField(null=True)
    question_5_answer = TextField(null=True)
    
    submitted_at = DateTimeField(default=datetime.now)
    reviewed_at = DateTimeField(null=True)
    reviewed_by = ForeignKeyField(User, null=True, backref='reviewed_applications')
    review_notes = TextField(null=True)
    
    class Meta:
        table_name = 'user_applications'
    
    def __str__(self):
        return f"Application for {self.user.name} - {self.status}"
