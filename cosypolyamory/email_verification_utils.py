"""
Utilities for email verification

This module provides secure token generation and verification for email changes.
Uses itsdangerous library for cryptographically signed tokens.
"""

import secrets
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app, url_for
from typing import Optional, Tuple
from cosypolyamory.models.email_verification import EmailVerification
from cosypolyamory.models.user import User


def get_serializer():
    """
    Get a URLSafeTimedSerializer instance using the app's secret key
    
    Returns:
        URLSafeTimedSerializer: Serializer for generating secure tokens
    """
    return URLSafeTimedSerializer(current_app.secret_key)


def generate_verification_token(user_id: str, new_email: str) -> str:
    """
    Generate a secure verification token
    
    This uses itsdangerous to create a cryptographically signed token that:
    - Cannot be forged without the secret key
    - Contains the user_id and new_email
    - Can be verified and decoded securely
    
    Args:
        user_id: The user's ID
        new_email: The new email address to verify
    
    Returns:
        str: A secure token string
    """
    serializer = get_serializer()
    
    # Create a payload with user_id, new_email, and a random salt
    # The salt adds extra randomness to prevent token reuse
    payload = {
        'user_id': user_id,
        'new_email': new_email,
        'salt': secrets.token_hex(16)
    }
    
    return serializer.dumps(payload, salt='email-verification')


def verify_verification_token(token: str, max_age: int = 86400) -> Optional[Tuple[str, str]]:
    """
    Verify and decode a verification token
    
    Args:
        token: The token to verify
        max_age: Maximum age of token in seconds (default: 86400 = 24 hours)
    
    Returns:
        tuple or None: (user_id, new_email) if valid, None if invalid/expired
    """
    serializer = get_serializer()
    
    try:
        payload = serializer.loads(
            token,
            salt='email-verification',
            max_age=max_age
        )
        return payload['user_id'], payload['new_email']
    except (SignatureExpired, BadSignature, KeyError):
        return None


def create_email_verification(user: User, new_email: str, hours_valid: int = 24) -> EmailVerification:
    """
    Create a new email verification record with a secure token
    
    Args:
        user: User object
        new_email: The new email address to verify
        hours_valid: Number of hours the token is valid (default: 24)
    
    Returns:
        EmailVerification: The created verification record
    """
    # Generate secure token
    token = generate_verification_token(user.id, new_email)
    
    # Cancel any existing pending verifications for this user
    EmailVerification.delete().where(
        (EmailVerification.user == user) & 
        (EmailVerification.is_used == False)
    ).execute()
    
    # Create new verification
    verification = EmailVerification.create_verification(
        user=user,
        new_email=new_email,
        token=token,
        hours_valid=hours_valid
    )
    
    return verification


def get_verification_url(token: str, _external: bool = True) -> str:
    """
    Generate the verification URL for a token
    
    Args:
        token: The verification token
        _external: Whether to generate an absolute URL (default: True)
    
    Returns:
        str: The verification URL
    """
    return url_for('auth.verify_email', token=token, _external=_external)


def verify_email_change(token: str) -> Tuple[bool, Optional[str], Optional[User]]:
    """
    Process an email verification
    
    This function:
    1. Validates the token cryptographically
    2. Checks if it exists in the database and is unused
    3. Verifies the token hasn't expired
    4. Updates the user's email if all checks pass
    5. Marks the verification as used
    
    Args:
        token: The verification token
    
    Returns:
        tuple: (success: bool, message: str, user: User or None)
    """
    # First verify the token cryptographically
    result = verify_verification_token(token)
    if not result:
        return False, "Invalid or expired verification link.", None
    
    user_id, new_email = result
    
    # Get the verification record from database
    verification = EmailVerification.get_valid_verification(token)
    if not verification:
        return False, "This verification link has expired or already been used.", None
    
    # Double-check the user_id matches
    if verification.user.id != user_id:
        return False, "Invalid verification link.", None
    
    # Double-check the email matches
    if verification.new_email != new_email:
        return False, "Invalid verification link.", None
    
    # Check if the new email is already in use by another user
    try:
        existing_user = User.get(User.email == new_email)
        if existing_user.id != user_id:
            verification.is_used = True
            verification.save()
            return False, "This email address is already in use by another account.", None
    except User.DoesNotExist:
        pass  # Email is available
    
    # All checks passed - update the user's email
    user = verification.user
    old_email = user.email
    user.email = new_email
    user.save()
    
    # Mark verification as used
    verification.is_used = True
    verification.verified_at = datetime.now()
    verification.save()
    
    return True, f"Your email has been successfully changed from {old_email} to {new_email}.", user


# Import datetime for verify_email_change
from datetime import datetime
