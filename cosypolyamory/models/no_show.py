"""
No-show tracking model for events
"""

from datetime import datetime
from peewee import ForeignKeyField, DateTimeField, CharField
from cosypolyamory.models import BaseModel
from cosypolyamory.models.user import User
from cosypolyamory.models.event import Event

class NoShow(BaseModel):
    """Track no-shows for specific events and users"""
    user = ForeignKeyField(User, backref='no_shows')
    event = ForeignKeyField(Event, backref='no_shows')
    marked_at = DateTimeField(default=datetime.now)
    marked_by = ForeignKeyField(User, backref='marked_no_shows')  # Admin who marked this
    notes = CharField(null=True, max_length=500)  # Optional notes about the no-show
    
    class Meta:
        table_name = 'no_shows'
        indexes = (
            # Ensure one no-show record per user per event
            (('user', 'event'), True),
        )
    
    def __str__(self):
        return f"NoShow({self.user.name} - {self.event.title})"
    
    def __repr__(self):
        return f"<NoShow: {self.user.id} at {self.event.id}>"
