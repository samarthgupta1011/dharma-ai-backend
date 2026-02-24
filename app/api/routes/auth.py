"""
app/api/routes/auth.py
──────────────────────
OTP-based mobile authentication endpoints.

Flow:
  1. Client calls POST /auth/request-otp with the user's mobile number.
     (In production this triggers an SMS via your provider of choice.)
  2. User reads OTP from SMS and submits it to POST /auth/verify-otp.
  3. Backend checks the OTP, creates a User document if one doesn't exist,
     and returns a short-lived access token + a long-lived refresh token.

Token lifecycle:
  • Access token  – 1-hour TTL. Sent on every API call.
  • Refresh token – 30-day TTL. Used only at POST /auth/refresh.
  • Token rotation – each /auth/refresh call issues a fresh pair and
    invalidates the previous refresh token (jti check on User document).
  • Single session – a new OTP login invalidates the previous refresh token.

OTP storage:
  Production implementation should store time-limited OTPs in Azure Cache
  for Redis (TTL = 10 minutes) keyed by mobile number.
  The current mock stores nothing — it accepts the hardcoded MOCK_OTP for
  any mobile number, which is fine for development.

Security notes:
  • The JWT `sub` claim carries the User's MongoDB ObjectId (not mobile).
  • Only the refresh token's JTI is persisted — the raw tokens are never stored.
  • OTPs themselves are never returned in any API response.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.models.user import User

_settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ── Dev constant ──────────────────────────────────────────────────────────────
# Replace with Redis-backed OTP store in production.
_MOCK_OTP = "123456"


# ── Request / Response schemas ────────────────────────────────────────────────

class OTPRequestBody(BaseModel):
    mobile: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{6,14}$",
        examples=["+919876543210"],
        description="E.164 formatted mobile number.",
    )


class OTPVerifyBody(BaseModel):
    mobile: str = Field(..., examples=["+919876543210"])
    otp: str = Field(..., min_length=4, max_length=8, examples=["123456"])


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool = Field(
        ...,
        description=(
            "True if this OTP verification created a new account. "
            "Use this flag in the React Native app to decide whether to "
            "navigate to the onboarding screen or the main dashboard."
        ),
    )


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="The refresh token issued by POST /auth/verify-otp or a previous POST /auth/refresh.")


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/request-otp",
    status_code=status.HTTP_200_OK,
    summary="Request a one-time password",
    response_description="Acknowledgement that an OTP was dispatched.",
)
async def request_otp(body: OTPRequestBody) -> dict:
    """
    Triggers an OTP dispatch to the supplied mobile number.

    **Production TODO:** Replace the stub below with a real SMS integration:
    ```python
    otp = generate_secure_otp()           # e.g. secrets.randbelow(900000) + 100000
    await redis.set(body.mobile, otp, ex=600)  # 10-minute TTL
    await sms_client.send(body.mobile, f"Your Dharma AI OTP is {otp}")
    ```
    """
    # --- MOCK IMPLEMENTATION ---
    # No SMS is sent; the hardcoded OTP (123456) is always valid.
    return {
        "status": "sent",
        "message": (
            f"OTP dispatched to {body.mobile}. "
            "[DEV MODE] Use OTP: 123456 to verify."
        ),
    }


@router.post(
    "/verify-otp",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP and obtain tokens",
    response_description="Access token, refresh token, and new-user flag.",
)
async def verify_otp(body: OTPVerifyBody) -> AuthResponse:
    """
    Validates the supplied OTP and issues a token pair.

    **If user does not exist:** a skeleton User document is created so the
    client receives valid tokens immediately. Profile completion happens
    asynchronously via PUT /users/me.

    **If user exists:** the existing document is returned — previous refresh
    token is invalidated (single-session model).

    Returns:
      - `access_token`: 1-hour JWT for API calls.
      - `refresh_token`: 30-day JWT for token rotation via POST /auth/refresh.
      - `is_new_user`: route to onboarding if True.
    """
    # --- MOCK OTP VALIDATION ---
    if body.otp != _MOCK_OTP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP. Please check the code and try again.",
        )

    # Upsert: fetch existing user or create a minimal new one.
    existing_user = await User.find_one(User.mobile == body.mobile)
    is_new_user = existing_user is None

    if is_new_user:
        new_user = User(mobile=body.mobile)
        await new_user.insert()
        user = new_user
    else:
        user = existing_user  # type: ignore[assignment]

    access_token = create_access_token(subject=str(user.id))
    refresh_token, jti = create_refresh_token(subject=str(user.id))

    # Persist the new session jti (overwrites any previous session).
    user.active_refresh_jti = jti
    user.refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(
        days=_settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    await user.save()

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        is_new_user=is_new_user,
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    status_code=status.HTTP_200_OK,
    summary="Rotate tokens using a refresh token",
    response_description="Fresh access token and rotated refresh token.",
)
async def refresh_tokens(body: RefreshRequest) -> TokenPair:
    """
    Issues a new access token and rotates the refresh token.

    The supplied refresh token is validated against the jti stored on the
    User document. On success, a fresh pair is returned and the previous
    refresh token is immediately invalidated (token rotation).

    Raises HTTP 401 if the refresh token is expired, invalid, or has already
    been rotated (replay detection).
    """
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_refresh_token(body.refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise _401

    user_id: str | None = payload.get("sub")
    jti: str | None = payload.get("jti")
    if not user_id or not jti:
        raise _401

    user = await User.get(user_id)
    if user is None or user.active_refresh_jti != jti:
        # Unknown user, or token was already rotated / session was logged out.
        raise _401

    # Issue a fresh token pair and rotate the stored jti.
    new_access_token = create_access_token(subject=user_id)
    new_refresh_token, new_jti = create_refresh_token(subject=user_id)

    user.active_refresh_jti = new_jti
    user.refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(
        days=_settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    await user.save()

    return TokenPair(access_token=new_access_token, refresh_token=new_refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Invalidate the current session",
    response_description="Confirmation that the session was cleared.",
)
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Clears the active refresh token jti from the User document, effectively
    invalidating the current session. The client should discard both tokens.
    """
    current_user.active_refresh_jti = None
    current_user.refresh_token_expires_at = None
    await current_user.save()
    return {"detail": "Logged out successfully."}
