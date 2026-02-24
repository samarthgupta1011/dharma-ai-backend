"""
app/models/user.py
──────────────────
Beanie Document model for the `users` MongoDB collection.

Design decisions:
  • `mobile` carries a unique sparse index (the primary login identifier).
  • All profile fields except `mobile` are Optional — a new user created
    at first OTP verification will have a skeleton document that they can
    fill in via PUT /users/me.
  • `UserStats` is an embedded sub-document (not a separate collection)
    because streak data is always read together with the user profile and
    it is private to that user.
"""

from datetime import date, datetime, timezone
from typing import Annotated, Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class UserStats(BaseModel):
    """
    Embedded document tracking the user's daily activity streak.

    Streak rules (enforced in POST /users/me/streak/increment):
      • Same day   → idempotent, no change.
      • +1 day gap → increment current_streak.
      • >1 day gap → streak broken, reset to 1.
    """

    current_streak: int = 0
    longest_streak: int = 0
    last_activity_date: Optional[date] = None


class User(Document):
    """
    Primary user entity stored in the `users` collection.

    The `mobile` field is the unique, canonical identifier — users log in
    via OTP to their mobile number.  All other profile fields are optional
    and collected progressively through the onboarding flow.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    mobile: Annotated[str, Indexed(unique=True)]

    # ── Profile (filled in gradually after signup) ────────────────────────────
    name: Optional[str] = None
    email: Optional[str] = None
    dob: Optional[date] = None
    city: Optional[str] = None

    # ── Metadata ──────────────────────────────────────────────────────────────
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # ── Embedded Gamification Stats ───────────────────────────────────────────
    stats: UserStats = Field(default_factory=UserStats)

    # ── Auth session (single active session per user) ─────────────────────────
    # The JTI (JWT ID) of the currently valid refresh token.
    # Cleared on logout; replaced on each new login or token rotation.
    active_refresh_jti: Optional[str] = None
    refresh_token_expires_at: Optional[datetime] = None

    class Settings:
        name = "users"
