"""
app/api/routes/recipe.py
─────────────────────────
The core personalisation endpoint: GET /recipe

Given a mood keyword and optional free-text feelings, this endpoint:
  1. Loads available PUNYA and BREATHING activities from the database
     and builds context strings for the AI.
  2. Calls OpenAI (or the mock service) to get a 4-category recipe:
     GITA verse, PUNYA activity, BREATHING exercise, and REFLECTIONS.
  3. Looks up the GITA verse, PUNYA activity, and BREATHING exercise
     from the database to merge DB-stored fields with AI-generated insights.
  4. Returns a keyed JSON object:
       {
         gita: { ... },
         punya: { ... },
         breathing: { ... },
         reflections: [ ... ],
         dummy_data: false  // true when OpenAI is disabled
       }

Fallback behaviour:
  • When ENABLE_OPENAI=false, the mock service returns dummy data.
    All text fields are suffixed with _DUMMY_ and `dummy_data: true`
    is set at the top level.
  • When the AI-recommended Gita verse is not found in the database,
    the response still includes the AI-generated deeper insights but
    marks `is_placeholder: true` on the gita object with helper text.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user
from app.models.ingredients import (
    Breathing,
    DeeperInsight,
    GitaVerse,
    ImpactPointer,
    Punya,
)
from app.models.recipe_request import RecipeRequest
from app.models.user import User
from app.services.ingredient_cache import CachedIngredient, get_ingredient_cache
from app.services.openai_service import BaseOpenAIService, get_openai_service
from app.services.storage_service import get_storage_service
from app.prompts.dharma_prompts import RECIPE_PROMPT_TEMPLATE

router = APIRouter(prefix="/recipe", tags=["Recipe"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_activity_context(
    activities: List[CachedIngredient],
) -> tuple[str, Dict[int, CachedIngredient]]:
    """
    Build a numbered context string and mapping for AI activity selection.

    Uses lightweight CachedIngredient projections (id, short_descp, location)
    rather than full DB documents.
    Returns (context_string, {number: cached_item}).
    """
    if not activities:
        return "(No activities available yet.)", {}

    lines: list[str] = []
    mapping: Dict[int, CachedIngredient] = {}
    for idx, activity in enumerate(activities, start=1):
        loc = f" [{activity.location}]" if activity.location else ""
        lines.append(f"{idx}.{loc} {activity.short_descp}")
        mapping[idx] = activity
    return "\n".join(lines), mapping


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.get(
    "/",
    summary="Get personalised spiritual recipe",
    response_description=(
        "A keyed JSON object with four categories: gita, punya, breathing, "
        "reflections. Includes `dummy_data: true` when OpenAI is disabled."
    ),
)
async def get_recipe(
    mood: str = Query(
        ...,
        description=(
            "The user's current emotional state. "
            "Example: 'anxious', 'grateful', 'lost', 'overwhelmed', 'peaceful'"
        ),
        examples=["anxious"],
    ),
    feelings: str = Query(
        default="",
        description=(
            "Optional free-text elaboration on the user's mood. "
            "Example: 'I keep replaying an argument from this morning.'"
        ),
    ),
    current_user: User = Depends(get_current_user),
    openai_service: BaseOpenAIService = Depends(get_openai_service),
) -> Dict[str, Any]:
    """
    Returns a 4-category spiritual recipe tailored to the user's mood.

    Flow:
      1. Load all PUNYA and BREATHING activities from DB
      2. Build context strings for the AI
      3. Call AI service (real or mock)
      4. Merge DB records with AI-generated insights
      5. Return keyed response with gita, punya, breathing, reflections
    """
    storage = get_storage_service()
    cache = get_ingredient_cache()

    # ── 1. Load available activities (from cache) ─────────────────────────────
    punya_cached = await cache.get("punya")
    breathing_cached = await cache.get("breathing")

    punya_context, punya_map = _build_activity_context(punya_cached)
    breathing_context, breathing_map = _build_activity_context(breathing_cached)

    # ── 2. Build user prompt & call AI service ────────────────────────────────
    feelings_line = f'The user adds: "{feelings}"' if feelings else ""
    user_prompt = RECIPE_PROMPT_TEMPLATE.format(
        mood=mood,
        feelings_line=feelings_line,
        punya_context=punya_context or "(No punya activities available in database yet.)",
        breathing_context=breathing_context or "(No breathing exercises available in database yet.)",
    )

    try:
        ai_recipe = await openai_service.generate_dharma_recipe(
            mood=mood,
            feelings=feelings,
            punya_context=punya_context,
            breathing_context=breathing_context,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recipe: {str(e)}",
        ) from e

    is_dummy = ai_recipe.get("dummy_data", False)

    # ── 2b. Log recipe request ────────────────────────────────────────────────
    await RecipeRequest(
        user_id=str(current_user.id),
        mood=mood,
        feelings=feelings,
        prompt=user_prompt,
    ).insert()

    # ── 3. Process GITA ──────────────────────────────────────────────────────
    gita_ai = ai_recipe["gita"]
    chapter = gita_ai["chapter"]
    verse_number = gita_ai["verse_number"]

    gita_verse = await GitaVerse.find_one(
        {"chapter": chapter, "verse_number": verse_number}
    )

    if gita_verse:
        # Overlay AI-generated fields onto the DB document
        gita_verse.deeper_insights_title = gita_ai.get("deeper_insights_title")
        gita_verse.deeper_insights = [
            DeeperInsight(**di) for di in gita_ai.get("deeper_insights", [])
        ]
        gita_dict = gita_verse.model_dump(mode="json")
        gita_dict = await storage.sign_media_fields(gita_dict)
        gita_dict["is_placeholder"] = False
    else:
        # Verse not in our DB — return AI insights with placeholder DB fields
        gita_dict = {
            "activity_type": "GITA",
            "title": f"Bhagavad Gita {chapter}.{verse_number}",
            "emoji": "🕉️",
            "subtitle": "Full verse details coming soon",
            "why": "This verse was selected by AI as relevant to your current mood.",
            "chapter": chapter,
            "verse_number": verse_number,
            "deeper_insights_title": gita_ai.get("deeper_insights_title"),
            "deeper_insights": gita_ai.get("deeper_insights", []),
            "sanskrit_text": "Verse text will be available soon",
            "transliteration": None,
            "english_translation": "Translation is being added to our library",
            "commentary": "Commentary is being added to our library",
            "audio_url": "",
            "icon_url": "",
            "is_placeholder": True,
        }

    # ── 4. Process PUNYA ──────────────────────────────────────────────────────
    punya_ai = ai_recipe["punya"]
    selected_punya_num = punya_ai.get("selected_number", 1)
    punya_cached_item = punya_map.get(selected_punya_num)
    punya_doc = (
        await Punya.get(punya_cached_item.id) if punya_cached_item else None
    )

    if punya_doc:
        punya_doc.ai_why = punya_ai.get("why")
        punya_doc.ai_impact = [
            ImpactPointer(**ip) for ip in punya_ai.get("impact", [])
        ]
        punya_dict = punya_doc.model_dump(mode="json")
        punya_dict = await storage.sign_media_fields(punya_dict)
    else:
        # No matching PUNYA doc — return AI-only data
        punya_dict = {
            "activity_type": "PUNYA",
            "title": "Act of Kindness",
            "emoji": "💛",
            "subtitle": "",
            "why": "Prosocial behaviour is the foundation of Dharma.",
            "activity": "",
            "ai_why": punya_ai.get("why", ""),
            "ai_impact": punya_ai.get("impact", []),
            "icon_url": "",
        }

    # ── 5. Process BREATHING ──────────────────────────────────────────────────
    breathing_ai = ai_recipe["breathing"]
    selected_breathing_num = breathing_ai.get("selected_number", 1)
    breathing_cached_item = breathing_map.get(selected_breathing_num)
    breathing_doc = (
        await Breathing.get(breathing_cached_item.id)
        if breathing_cached_item
        else None
    )

    if breathing_doc:
        breathing_doc.ai_why = breathing_ai.get("why")
        breathing_doc.ai_impact = [
            ImpactPointer(**ip) for ip in breathing_ai.get("impact", [])
        ]
        breathing_dict = breathing_doc.model_dump(mode="json")
        breathing_dict = await storage.sign_media_fields(breathing_dict)
    else:
        # No matching BREATHING doc — return AI-only data
        breathing_dict = {
            "activity_type": "BREATHING",
            "title": "Breathing Exercise",
            "emoji": "🧘",
            "subtitle": "",
            "why": "Controlled breathing activates the vagus nerve.",
            "ai_why": breathing_ai.get("why", ""),
            "ai_impact": breathing_ai.get("impact", []),
            "icon_url": "",
        }

    # ── 6. Process REFLECTIONS ────────────────────────────────────────────────
    reflections_ai = ai_recipe.get("reflections", [])
    reflections_list = [
        {"emoji": r.get("emoji", "🪷"), "question": r.get("question", "")}
        for r in reflections_ai
    ]

    # ── 7. Assemble final response ────────────────────────────────────────────
    return {
        "gita": gita_dict,
        "punya": punya_dict,
        "breathing": breathing_dict,
        "reflections": reflections_list,
        "dummy_data": is_dummy,
    }

