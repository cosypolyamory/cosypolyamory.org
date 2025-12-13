"""
Email verification model for secure email changes
"""

from datetime import datetime, timedelta
from peewee import CharField, DateTimeField, ForeignKeyField, BooleanField
from cosypolyamory.models import BaseModel
from cosypolyamory.models.user import User


class EmailVerification(BaseModel):
    """Model for tracking pending email verifications"""
    
    user = ForeignKeyField(User, backref='email_verifications', on_delete='CASCADE')
    new_email = CharField()  # The email address to be verified
    token = CharField(unique=True, index=True)  # Secure verification token
    created_at = DateTimeField(default=datetime.now)
    expires_at = DateTimeField()  # Token expiration time
    verified_at = DateTimeField(null=True)  # When the verification was completed
    is_used = BooleanField(default=False)  # Whether the token has been used
    
    class Meta:
        table_name = 'email_verifications'
    
    def __str__(self):
        return f"EmailVerification({self.user.email} -> {self.new_email})"
    
    def __repr__(self):
        return f"<EmailVerification: {self.user.id} -> {self.new_email}>"
    
    def is_expired(self):
        """Check if the verification token has expired"""
        return datetime.now() > self.expires_at
    
    def is_valid(self):
        """Check if the token is still valid (not expired and not used)"""
        return not self.is_expired() and not self.is_used
    
    @classmethod
    def create_verification(cls, user, new_email, token, hours_valid=24):
        """
        Create a new email verification record
        
        Args:
            user: User object
            new_email: The new email address to verify
            token: Secure verification token
            hours_valid: Number of hours the token is valid (default: 24)
        
        Returns:
            EmailVerification: The created verification record
        """
        expires_at = datetime.now() + timedelta(hours=hours_valid)
        return cls.create(
            user=user,
            new_email=new_email,
            token=token,
            expires_at=expires_at
        )
    
    @classmethod
    def get_valid_verification(cls, token):
        """
        Get a valid verification by token
        
        Args:
            token: The verification token
        
        Returns:
            EmailVerification or None: The verification if valid, None otherwise
        """
        try:
            verification = cls.get(cls.token == token)
            if verification.is_valid():
                return verification
            return None
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def cleanup_expired(cls, days_old=7):
        """
        Delete expired verification records older than specified days
        
        Args:
            days_old: Delete records older than this many days (default: 7)
        
        Returns:
            int: Number of records deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days_old)
        deleted = cls.delete().where(cls.expires_at < cutoff_date).execute()
        return deleted
