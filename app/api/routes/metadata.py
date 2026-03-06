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
        "label": "Anxious",
        "emoji": "😰",
        "description": "Racing thoughts, tight chest",
        "ai_hint": "User is experiencing anxiety, worry, or stress.",
    },
    {
        "value": "low",
        "label": "Low",
        "emoji": "🥺",
        "description": "Heavy, unmotivated",
        "ai_hint": "User feels low, melancholic, or depressed.",
    },
    {
        "value": "scattered",
        "label": "Scattered",
        "emoji": "🌀",
        "description": "Can't focus, restless",
        "ai_hint": "User feels scattered, restless, unable to concentrate.",
    },
    {
        "value": "grateful",
        "label": "Grateful",
        "emoji": "🙏",
        "description": "Good energy, thankful",
        "ai_hint": "User is in a positive, grateful, or joyful state.",
    },
    {
        "value": "tired",
        "label": "Tired",
        "emoji": "🥱",
        "description": "Drained, need rest",
        "ai_hint": "User feels exhausted, drained, needs recovery.",
    },
    {
        "value": "curious",
        "label": "Curious",
        "emoji": "🔮",
        "description": "Ready to explore",
        "ai_hint": "User is intellectually curious and open to exploration.",
    },
    {
        "value": "not_sure",
        "label": "Not sure how I'm feeling",
        "emoji": "🤷",
        "description": "Just here, open",
        "ai_hint": "User is unsure of their emotional state; provide gentle, exploratory guidance.",
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
