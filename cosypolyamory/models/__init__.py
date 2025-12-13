"""
Base model for all database models
"""

from peewee import Model
from cosypolyamory.database import database

class BaseModel(Model):
    """Base model class that all models should inherit from"""
    
    class Meta:
        database = database

# Import models here for easy access
from cosypolyamory.models.email_verification import EmailVerification
