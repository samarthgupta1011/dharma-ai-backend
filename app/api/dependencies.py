"""
app/api/dependencies.py
────────────────────────
FastAPI dependency injection providers.

Two dependency families live here:

  1. Authentication  ──  get_current_user
     Validates the JWT Bearer token from the Authorization header and
     resolves it to a live User document from MongoDB.
     Any route that `Depends(get_current_user)` is automatically protected.

  2. AI Engine  ──  get_ai_engine
     Returns the active AIEngine implementation.
     Swapping from MockAIEngine to ClaudeAIEngine is a one-line change here;
     zero route code needs to be touched.
"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.models.user import User
from app.services.ai_service import AIEngine, MockAIEngine

# ── JWT Bearer extraction ─────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(
    scheme_name="JWT Bearer",
    description="Paste your access token from POST /auth/verify-otp.",
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> User:
    """
    FastAPI dependency that authenticates the caller via JWT.

    Flow:
      1. HTTPBearer extracts the token from `Authorization: Bearer <token>`.
      2. decode_access_token validates signature and expiry.
      3. The `sub` claim (User ObjectId string) is used to fetch the User
         document from MongoDB via Beanie.

    Raises:
      HTTP 401 – token missing, expired, signature invalid, or user not found.
      HTTP 403 – automatically raised by HTTPBearer if the header is absent.

    Returns:
      The fully-populated User Beanie document for the authenticated caller.
    """
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise _401
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired. Use POST /auth/refresh to obtain a new one.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise _401

    user = await User.get(user_id)
    if user is None:
        # Token was valid but the account was deleted — treat as unauthorised.
        raise _401

    return user


# ── AI Engine ─────────────────────────────────────────────────────────────────

def get_ai_engine() -> AIEngine:
    """
    FastAPI dependency that supplies the active AIEngine implementation.

    To upgrade to a production LLM engine:
      1. Implement a new class inheriting AIEngine in app/services/ai_service.py.
      2. Replace `MockAIEngine()` with your new class below.
      3. Deploy — no route code changes required.
    """
    return MockAIEngine()
