"""
app/core/security.py
────────────────────
JWT utility functions for the Dharma AI backend.

Tokens are HS256-signed JWTs.  The payload carries:
  • sub  – the MongoDB ObjectId string of the authenticated User document.
  • iat  – issued-at timestamp (UTC).
  • exp  – expiry timestamp (UTC).

All functions raise standard Python exceptions; the HTTP translation
(401 Unauthorized) is handled by the dependency in api/dependencies.py.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.core.config import get_settings

settings = get_settings()


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Mints a signed JWT access token.

    Args:
        subject:       The value for the `sub` claim (User ObjectId string).
        expires_delta: Optional custom TTL.  Defaults to
                       JWT_ACCESS_TOKEN_EXPIRE_MINUTES from settings.

    Returns:
        A compact, URL-safe JWT string.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError:     If the token is malformed or the signature
                                   is invalid.

    Returns:
        The decoded payload dictionary.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
