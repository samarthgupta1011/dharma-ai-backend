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

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user
from app.models.ingredients import BaseIngredient
from app.models.user import User

router = APIRouter(prefix="/recipe", tags=["Recipe"])


@router.get(
    "/",
    summary="Get all spiritual ingredients",
    response_description=(
        "A heterogeneous list of all ingredient objects. "
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
            "Will be used for AI-based personalisation in a future iteration.  "
            "Example: 'I keep replaying an argument from this morning.'"
        ),
    ),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Returns all ingredients from the database.
    `mood` and `feelings` params are accepted but not yet used —
    AI-based personalisation will be wired in a future iteration.
    """
    ingredients = await BaseIngredient.find(with_children=True).to_list()  # type: ignore[union-attr]
    return [ingredient.model_dump(mode="json") for ingredient in ingredients]
