"""
RSVP model for event attendance
"""

from datetime import datetime
from peewee import CharField, TextField, DateTimeField, BooleanField, ForeignKeyField
from cosypolyamory.models import BaseModel
from cosypolyamory.models.user import User
from cosypolyamory.models.event import Event

class RSVP(BaseModel):
    """Event RSVP model"""
    event = ForeignKeyField(Event, backref='rsvps')
    user = ForeignKeyField(User, backref='rsvps')
    
    status = CharField(choices=[
        ('yes', 'Attending'),
        ('no', 'Not Attending'),
        ('maybe', 'Maybe'),
        ('waitlist', 'Waitlisted')
    ])
    
    notes = TextField(null=True)  # Optional notes from user
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'rsvps'
        indexes = (
            (('event', 'user'), True),  # Unique constraint: one RSVP per user per event
        )
    
    def __str__(self):
        return f"{self.user.name} - {self.event.title} ({self.status})"
