"""
app/api/routes/recipe.py
─────────────────────────
The core personalisation endpoint: GET /recipe

This is the central value proposition of Dharma AI.  Given a mood keyword
and optional free-text feelings, the injected AIEngine selects a curated
mix of spiritual ingredients (yoga, verse, breathing, mantra, deed, story)
tailored to the user's current state.

Design decisions:
  • The endpoint accepts both `mood` and `feelings` as query parameters to
    keep it stateless and easily cacheable at the CDN layer in future.
  • The response is a heterogeneous JSON array — each element may have
    different fields depending on its `activity_type`.  This is intentional:
    the React Native client uses the `activity_type` discriminator to render
    the correct card component for each ingredient.
  • The route is JWT-protected so future versions can personalise based on
    the user's history, preferences, and streak data.
  • The AI engine is injected via Depends — swapping MockAIEngine for a real
    LLM requires changing exactly one line in app/api/dependencies.py.
"""

from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_ai_engine, get_current_user
from app.models.user import User
from app.services.ai_service import AIEngine

router = APIRouter(prefix="/recipe", tags=["Recipe"])


@router.get(
    "/",
    summary="Generate a personalised spiritual recipe",
    response_description=(
        "A heterogeneous list of ingredient objects. "
        "Each item includes an `activity_type` field that the frontend "
        "uses to render the correct card component."
    ),
)
async def get_recipe(
    mood: str = Query(
        ...,
        description=(
            "The user's current emotional state.  Must be one of the values "
            "returned by GET /metadata/configs under the `moods` key.  "
            "Example: 'anxious', 'grateful', 'lost'"
        ),
        examples=["anxious"],
    ),
    feelings: str = Query(
        default="",
        description=(
            "Optional free-text elaboration on the user's mood.  "
            "The AI engine uses this for finer-grained personalisation.  "
            "Example: 'I keep replaying an argument from this morning.'"
        ),
    ),
    current_user: User = Depends(get_current_user),
    ai_engine: AIEngine = Depends(get_ai_engine),
) -> List[Dict[str, Any]]:
    """
    Returns a personalised 'recipe' — a curated list of spiritual activities
    and content items recommended based on the user's mood and feelings.

    **Response shape (per element):**

    All elements share a common base:
    ```json
    {
      "id": "<MongoDB ObjectId>",
      "activity_type": "YOGA | GITA | BREATHING | MANTRA | GOOD_DEED | STORY",
      "title": "...",
      "why": "Scientific/historical rationale...",
      "tags": {"anxiety": 0.9, "stress": 0.8},
      "icon_url": "https://..."
    }
    ```

    Plus type-specific fields:
    - `YOGA` adds: `gif_url`, `steps`, `anatomical_focus`
    - `GITA` adds: `sanskrit_text`, `transliteration`, `english_translation`,
                   `commentary`, `audio_url`
    - `BREATHING` adds: `audio_url`, `duration_seconds`, `pattern`
    - `MANTRA` adds: `audio_url`, `mantra_text`, `frequency_hz`
    - `GOOD_DEED` adds: `task_description`, `impact_logic`
    - `STORY` adds: `story_text`, `scripture_source`, `image_url`
    """
    ingredients = await ai_engine.generate_recipe(mood=mood, feelings=feelings)

    # Serialize to plain dicts so FastAPI's JSON encoder handles ObjectIds,
    # dates, and all Pydantic types correctly.
    return [ingredient.model_dump(mode="json") for ingredient in ingredients]
