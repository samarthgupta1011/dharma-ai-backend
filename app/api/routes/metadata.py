"""
app/api/routes/metadata.py
───────────────────────────
System configuration sync endpoint.

GET /metadata/configs is the single source of truth for all enum values
and app constants consumed by the React Native frontend.

Why this pattern matters:
  Without this endpoint, enums must be duplicated in both the backend
  (Python) and the frontend (TypeScript).  Any time a new ActivityType or
  Mood is added, both codebases must be updated in sync — a classic source
  of drift bugs.

  With this endpoint, the frontend fetches config at startup and uses
  the dynamic values everywhere.  Adding a new enum value here
  automatically propagates to the frontend on the next app launch —
  no frontend deployment required.

Public endpoint — no JWT required.
"""

from typing import Any, Dict, List

from fastapi import APIRouter

from app.config.settings import get_settings
from app.models.ingredients import ActivityType

router = APIRouter(prefix="/metadata", tags=["Metadata"])

settings = get_settings()

# ── Mood definitions ──────────────────────────────────────────────────────────
# Each mood maps to:
#   • value:   the string the frontend sends to GET /recipe?mood=<value>
#   • label:   the human-readable string shown in the UI
#   • emoji:   optional decorative element for the mood picker screen
#   • ai_hint: a descriptor the AI engine can use to refine matching

_MOODS: List[Dict[str, str]] = [
    {
        "value": "anxious",
        "label": "Anxious / Stressed",
        "emoji": "😰",
        "ai_hint": "User is experiencing anxiety, worry, or stress.",
    },
    {
        "value": "sad",
        "label": "Sad / Low",
        "emoji": "😔",
        "ai_hint": "User feels low, melancholic, or depressed.",
    },
    {
        "value": "grateful",
        "label": "Grateful / Happy",
        "emoji": "🙏",
        "ai_hint": "User is in a positive, grateful, or joyful state.",
    },
    {
        "value": "lost",
        "label": "Lost / Confused",
        "emoji": "🌫️",
        "ai_hint": "User feels directionless, confused about life choices.",
    },
    {
        "value": "angry",
        "label": "Angry / Frustrated",
        "emoji": "😤",
        "ai_hint": "User is experiencing anger or frustration.",
    },
    {
        "value": "curious",
        "label": "Curious / Seeking",
        "emoji": "🔍",
        "ai_hint": "User is intellectually curious and open to exploration.",
    },
    {
        "value": "peaceful",
        "label": "Peaceful / Content",
        "emoji": "☮️",
        "ai_hint": "User is calm and wants to deepen their sense of stillness.",
    },
]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/configs",
    summary="Fetch all app configuration enums",
    response_description=(
        "A single JSON object containing all enum sets and constants "
        "the frontend needs to function correctly."
    ),
)
async def get_app_configs() -> Dict[str, Any]:
    """
    Returns all system enumerations and configuration constants.

    **Frontend usage pattern:**
    ```typescript
    const { activity_types, moods } = await api.get('/metadata/configs');
    // Use activity_types to map API responses to card components.
    // Use moods to populate the mood-picker screen dynamically.
    ```

    **Response structure:**
    ```json
    {
      "activity_types": [
        { "value": "YOGA", "label": "Yoga" },
        ...
      ],
      "moods": [
        { "value": "anxious", "label": "Anxious / Stressed", "emoji": "😰" },
        ...
      ],
      "app_version": "1.0.0"
    }
    ```
    """
    return {
        "activity_types": [
            {
                "value": at.value,
                "label": at.value.replace("_", " ").title(),
            }
            for at in ActivityType
        ],
        "moods": _MOODS,
        "app_version": settings.APP_VERSION,
    }
