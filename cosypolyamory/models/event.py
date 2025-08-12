"""
Event model for community events
"""

from datetime import datetime
from peewee import CharField, TextField, DateTimeField, BooleanField, ForeignKeyField, IntegerField
from cosypolyamory.models import BaseModel
from cosypolyamory.models.user import User

class Event(BaseModel):
    """Community event model"""
    title = CharField()
    description = TextField()
    
    # Public info (visible to non-approved users)
    barrio = CharField()  # Area/neighborhood (changed from postcode_area)
    time_period = CharField()
    date = DateTimeField()
    
    # Private info (only for approved users)
    establishment_name = CharField()  # Name of the place/venue
    google_maps_link = TextField()  # Required Google Maps link
    location_notes = TextField(null=True)  # Additional directions
    exact_time = DateTimeField()  # Exact start time
    end_time = DateTimeField(null=True)  # Optional end time
    
    # Event management
    organizer = ForeignKeyField(User, backref='organized_events')
    co_host = ForeignKeyField(User, null=True, backref='co_hosted_events')
    
    # Event settings
    max_attendees = IntegerField(null=True)  # Optional capacity limit
    tips_for_attendees = TextField(null=True)  # Changed from requirements
    is_active = BooleanField(default=True)
    requires_approval = BooleanField(default=True)  # Only approved users can see full details
    
    # Metadata
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'events'
    
    def __str__(self):
        return f"{self.title} - {self.date.strftime('%Y-%m-%d')}"
    
    def get_public_time_display(self):
        """Get time display for non-approved users"""
        return f"{self.time_period.title()} on {self.date.strftime('%B %d, %Y')}"
    
    def get_full_time_display(self):
        """Get full time display for approved users"""
        return f"{self.exact_time.strftime('%H:%M')} on {self.exact_time.strftime('%B %d, %Y')}"
