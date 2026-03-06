"""
app/models/recipe_request.py
─────────────────────────────
Beanie Document for logging every recipe generation request.

Stores the user's mood, feelings, and the prompt that was sent to the
AI service.  Useful for analytics, debugging AI output quality, and
understanding user patterns over time.
"""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document, Indexed
from pydantic import Field


class RecipeRequest(Document):
    """
    An immutable log entry created each time GET /recipe is called.

    Fields:
      • user_id  — reference to the requesting user (indexed for per-user queries).
      • mood     — the mood keyword supplied by the client.
      • feelings — optional free-text elaboration.
      • prompt   — the full user-message string sent to OpenAI / mock service.
      • created_at — UTC timestamp of the request.
    """

    user_id: Indexed(str)  # type: ignore[valid-type]
    mood: str
    feelings: str = ""
    prompt: str = ""
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    class Settings:
        name = "recipe_requests"
