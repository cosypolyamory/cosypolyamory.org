"""
User model for OAuth authentication
"""

from datetime import datetime
from peewee import CharField, DateTimeField, BooleanField
from flask_login import UserMixin
from cosypolyamory.models import BaseModel

class User(UserMixin, BaseModel):
    """User model for OAuth authentication"""
    id = CharField(primary_key=True)  # This will be "google_123456" or "github_789"
    email = CharField(unique=True)
    name = CharField()
    avatar_url = CharField(null=True)
    provider = CharField()  # 'google' or 'github'
    created_at = DateTimeField(default=datetime.now)
    last_login = DateTimeField(default=datetime.now)
    
    # User roles and status
    is_admin = BooleanField(default=False)
    is_organizer = BooleanField(default=False)
    is_approved = BooleanField(default=False)  # Whether user passed community approval
    role = CharField(default='pending')  # 'admin', 'organizer', 'approved', 'pending'
    
    class Meta:
        table_name = 'users'
    
    def __str__(self):
        return f"User({self.name} - {self.email})"
    
    def __repr__(self):
        return f"<User: {self.id} ({self.provider})>"
    
    def get_role_display(self):
        """Get user role for display"""
        role = getattr(self, 'role', 'pending')
        if role == 'admin':
            return "Admin"
        elif role == 'organizer':
            return "Organizer"
        elif role == 'approved':
            return "Member"
        elif role == 'rejected':
            return "Rejected"
        else:
            return "Pending Approval"
    
    def can_organize_events(self):
        """Check if user can organize events"""
        return self.is_organizer or self.is_admin
    
    def can_see_full_event_details(self):
        """Check if user can see full event details"""
        return self.is_approved or self.is_organizer or self.is_admin
