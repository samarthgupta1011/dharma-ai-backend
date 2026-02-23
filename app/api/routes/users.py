"""
app/api/routes/users.py
────────────────────────
User profile and streak management endpoints.

All endpoints in this module are JWT-protected via `get_current_user`.

Streak logic (POST /users/me/streak/increment):
  ┌──────────────────────────────┬─────────────────────────────────────┐
  │ last_activity_date condition │ Action                              │
  ├──────────────────────────────┼─────────────────────────────────────┤
  │ == today                     │ Idempotent — no change.             │
  │ == yesterday                 │ current_streak += 1                 │
  │ Older or None                │ Streak broken → current_streak = 1  │
  └──────────────────────────────┴─────────────────────────────────────┘
  After each valid increment, longest_streak is updated if current > longest.

  The streak endpoint is intentionally separate from content endpoints so
  the mobile client can call it once per session without coupling it to
  any specific activity type.
"""

from datetime import date, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from app.api.dependencies import get_current_user
from app.models.user import User, UserStats

router = APIRouter(prefix="/users", tags=["Users"])


# ── Request / Response schemas ────────────────────────────────────────────────

class UserUpdateBody(BaseModel):
    """
    All fields are optional so the client can do partial updates (PATCH-style
    semantics over PUT — simpler for the mobile client to reason about).
    """
    name: Optional[str] = Field(default=None, examples=["Arjuna Sharma"])
    email: Optional[str] = Field(default=None, examples=["arjuna@example.com"])
    dob: Optional[date] = Field(default=None, examples=["1995-06-15"])
    city: Optional[str] = Field(default=None, examples=["Mumbai"])


class UserStatsOut(BaseModel):
    current_streak: int
    longest_streak: int
    last_activity_date: Optional[date]


class UserOut(BaseModel):
    id: str
    mobile: str
    name: Optional[str]
    email: Optional[str]
    dob: Optional[date]
    city: Optional[str]
    created_at: datetime
    stats: UserStatsOut

    @classmethod
    def from_document(cls, user: User) -> "UserOut":
        return cls(
            id=str(user.id),
            mobile=user.mobile,
            name=user.name,
            email=user.email,
            dob=user.dob,
            city=user.city,
            created_at=user.created_at,
            stats=UserStatsOut(
                current_streak=user.stats.current_streak,
                longest_streak=user.stats.longest_streak,
                last_activity_date=user.stats.last_activity_date,
            ),
        )


class StreakOut(BaseModel):
    current_streak: int
    longest_streak: int
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current user profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    """Returns the full profile of the authenticated user."""
    return UserOut.from_document(current_user)


@router.put(
    "/me",
    response_model=UserOut,
    summary="Update current user profile",
)
async def update_me(
    body: UserUpdateBody,
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    """
    Updates the authenticated user's profile.

    Only the fields supplied in the request body are written; omitted fields
    retain their current values.  Supplying `null` for a field clears it.
    """
    update_data = body.model_dump(exclude_unset=True)

    if update_data:
        await current_user.set(update_data)
        # Re-fetch to get the latest state after the update.
        await current_user.sync()

    return UserOut.from_document(current_user)


@router.post(
    "/me/streak/increment",
    response_model=StreakOut,
    summary="Increment daily activity streak",
)
async def increment_streak(
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreakOut:
    """
    Records today's activity and updates the streak counter.

    **Idempotent:** Calling this endpoint multiple times on the same day
    returns the current streak without further incrementing it.

    **Streak rules:**
    - Called on the same day as `last_activity_date` → no change.
    - Called exactly one day after `last_activity_date` → streak incremented.
    - Called after a gap of more than one day → streak reset to 1.
    """
    today = date.today()
    stats: UserStats = current_user.stats

    # ── Idempotency guard ─────────────────────────────────────────────────────
    if stats.last_activity_date == today:
        return StreakOut(
            current_streak=stats.current_streak,
            longest_streak=stats.longest_streak,
            message="Activity already recorded for today. Keep the momentum!",
        )

    # ── Streak calculation ────────────────────────────────────────────────────
    if stats.last_activity_date is not None:
        gap_days = (today - stats.last_activity_date).days
        if gap_days == 1:
            stats.current_streak += 1
        else:
            # Streak broken — restart from 1.
            stats.current_streak = 1
    else:
        # First ever activity.
        stats.current_streak = 1

    stats.last_activity_date = today
    stats.longest_streak = max(stats.longest_streak, stats.current_streak)

    await current_user.set({"stats": stats.model_dump()})

    return StreakOut(
        current_streak=stats.current_streak,
        longest_streak=stats.longest_streak,
        message="Streak updated. Well done!",
    )
