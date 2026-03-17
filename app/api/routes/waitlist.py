"""
app/api/routes/waitlist.py
──────────────────────────
Public waitlist signup endpoint for the myDharma website.

No authentication required. Rate-limited to 5 requests per IP per minute.
Duplicate emails are silently accepted (returns 200, not an error).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from pymongo.errors import DuplicateKeyError

from app.core.rate_limit import RateLimiter
from app.models.waitlist import WaitlistEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Waitlist"])

_rate_limiter = RateLimiter(max_calls=5, window_seconds=60)


class WaitlistRequest(BaseModel):
    email: EmailStr = Field(..., examples=["user@example.com"])


class WaitlistResponse(BaseModel):
    success: bool
    message: str


@router.post(
    "/waitlist",
    response_model=WaitlistResponse,
    status_code=status.HTTP_200_OK,
    summary="Join the waitlist",
    response_description="Confirmation that the email was recorded.",
    dependencies=[Depends(_rate_limiter)],
)
async def join_waitlist(body: WaitlistRequest) -> WaitlistResponse:
    """
    Adds an email to the myDharma launch waitlist.

    - Validates the email format.
    - If the email already exists, returns 200 (not an error).
    - Rate-limited to 5 requests per IP per minute.
    """
    try:
        entry = WaitlistEntry(email=body.email)
        await entry.insert()
    except DuplicateKeyError:
        # Silently accept duplicates — don't reveal whether the email exists
        pass
    except Exception:
        logger.exception("Failed to save waitlist entry")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Please try again.",
        )

    return WaitlistResponse(
        success=True,
        message="You're on the list!",
    )
