"""
app/core/security.py
────────────────────
JWT utility functions for the Dharma AI backend.

Two token types are issued:

  Access token  – short-lived (1 hour). Sent on every API call via
                  Authorization: Bearer.  Payload: sub, iat, exp.

  Refresh token – long-lived (30 days). Stored server-side (jti only).
                  Used exclusively at POST /auth/refresh to rotate tokens.
                  Payload: sub, type="refresh", jti, iat, exp.

All functions raise standard Python exceptions; the HTTP translation
(401 Unauthorized) is handled by the dependency in api/dependencies.py.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.config.settings import get_settings

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


def create_refresh_token(subject: str) -> tuple[str, str]:
    """
    Mints a signed JWT refresh token with a unique JTI claim.

    Args:
        subject: The value for the `sub` claim (User ObjectId string).

    Returns:
        A tuple of (signed_jwt, jti_string).
        Store only the jti on the User document — never the raw token.
    """
    jti = str(uuid.uuid4())
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": subject,
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + expires_delta,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_refresh_token(token: str) -> dict:
    """
    Decodes and validates a JWT refresh token.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError:     If the token is malformed, signature invalid,
                                   or the `type` claim is not "refresh".

    Returns:
        The decoded payload dictionary (includes sub, jti, type, iat, exp).
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Not a refresh token.")
    return payload
