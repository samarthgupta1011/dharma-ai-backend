"""
app/api/routes/auth.py
──────────────────────
OTP-based mobile authentication endpoints.

Flow:
  1. Client calls POST /auth/request-otp with the user's mobile number.
     (In production this triggers an SMS via your provider of choice.)
  2. User reads OTP from SMS and submits it to POST /auth/verify-otp.
  3. Backend checks the OTP, creates a User document if one doesn't exist,
     and returns a signed JWT access token.

OTP storage:
  Production implementation should store time-limited OTPs in Azure Cache
  for Redis (TTL = 10 minutes) keyed by mobile number.
  The current mock stores nothing — it accepts the hardcoded MOCK_OTP for
  any mobile number, which is fine for development.

Security notes:
  • The JWT `sub` claim carries the User's MongoDB ObjectId (not mobile).
  • Access tokens expire after JWT_ACCESS_TOKEN_EXPIRE_MINUTES (default 7 days).
  • OTPs themselves are never returned in any API response.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import create_access_token
from app.models.user import User

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
    token_type: str = "bearer"
    is_new_user: bool = Field(
        ...,
        description=(
            "True if this OTP verification created a new account. "
            "Use this flag in the React Native app to decide whether to "
            "navigate to the onboarding screen or the main dashboard."
        ),
    )


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
    summary="Verify OTP and obtain a JWT",
    response_description="JWT access token and new-user flag.",
)
async def verify_otp(body: OTPVerifyBody) -> AuthResponse:
    """
    Validates the supplied OTP.

    **If user does not exist:** a skeleton User document is created so the
    client receives a valid token immediately.  Profile completion happens
    asynchronously via PUT /users/me.

    **If user exists:** the existing document is returned — no mutation.

    Returns a signed JWT (7-day TTL by default) and the `is_new_user` flag.
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

    return AuthResponse(
        access_token=access_token,
        is_new_user=is_new_user,
    )
