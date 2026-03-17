"""
app/models/waitlist.py
──────────────────────
Waitlist signup model for the myDharma website.

Stores email addresses of users who want to be notified at launch.
The email field has a unique index to silently reject duplicates at
the database level.
"""

from datetime import datetime, timezone

from beanie import Document
from pymongo import IndexModel, ASCENDING
from pydantic import EmailStr, Field


class WaitlistEntry(Document):
    email: EmailStr = Field(..., description="Email address of the waitlist subscriber.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = Field(default="website", description="Where the signup came from.")

    class Settings:
        name = "waitlist"
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True),
        ]
