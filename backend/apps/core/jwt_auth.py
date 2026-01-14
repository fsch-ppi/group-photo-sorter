"""
JWT-based session authentication for secure 7-day sessions.
"""

import jwt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from django.conf import settings
from django.contrib.auth.models import User


# Session duration
SESSION_DURATION_DAYS = 7


def generate_session_token(user: User) -> str:
    """
    Generate a secure JWT session token for the user.

    The token contains:
    - user_id: The user's database ID
    - username: For quick access without DB lookup
    - jti: Unique token ID to prevent replay attacks
    - iat: Issued at timestamp
    - exp: Expiration timestamp (7 days)
    """
    now = datetime.now(timezone.utc)
    payload = {
        'user_id': user.id,
        'username': user.username,
        'jti': secrets.token_hex(16),  # Unique token ID
        'iat': now,
        'exp': now + timedelta(days=SESSION_DURATION_DAYS),
        'type': 'session',
    }

    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm='HS256'
    )

    return token


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a JWT session token.

    Returns the payload if valid, None if invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256'],
            options={
                'require': ['user_id', 'username', 'jti', 'iat', 'exp', 'type'],
            }
        )

        # Verify token type
        if payload.get('type') != 'session':
            return None

        return payload

    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user_from_token(token: str) -> Optional[User]:
    """
    Get the User object from a valid session token.
    """
    payload = verify_session_token(token)
    if not payload:
        return None

    try:
        user = User.objects.get(id=payload['user_id'])
        # Verify username hasn't changed (extra security)
        if user.username != payload['username']:
            return None
        return user
    except User.DoesNotExist:
        return None


def get_token_expiry_info(token: str) -> Optional[Dict[str, Any]]:
    """
    Get expiry information for a token without full validation.
    Useful for frontend to know when to refresh.
    """
    try:
        # Decode without verification to get expiry
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256'],
            options={'verify_exp': False}
        )

        exp = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        return {
            'expires_at': exp.isoformat(),
            'expires_in_seconds': max(0, int((exp - now).total_seconds())),
            'is_expired': now > exp,
        }
    except jwt.InvalidTokenError:
        return None
