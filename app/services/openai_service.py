"""
app/services/openai_service.py
──────────────────────────────
Service for generating personalised spiritual recipes using OpenAI's API
or deterministic mock data (when ENABLE_OPENAI is false).

Architecture:
  • `BaseOpenAIService`: Abstract base class defining the interface
  • `OpenAIService`: Production class making real OpenAI API calls with
    guardrails enforced via a system prompt
  • `MockOpenAIService`: Development class returning hardcoded dummy data
    (no API call). All text fields are suffixed with _DUMMY_ and the
    response includes `dummy_data: true` so callers can detect it.
  • `get_openai_service()`: Factory that returns the appropriate service
    based on the ENABLE_OPENAI flag.

Design decisions:
  • Uses strategy pattern for transparent switching between real and mock
  • System prompt contains strict guardrails (Hindu scriptures only, no
    self-harm, safe emojis, etc.) — defined in app/prompts/dharma_prompts.py
  • User prompt is the recipe-generation template with mood, feelings,
    and available activities injected at call time
  • Async/await with OpenAI's AsyncOpenAI to avoid blocking the event loop
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from openai import AsyncOpenAI

from app.config.settings import get_settings
from app.prompts.dharma_prompts import RECIPE_PROMPT_TEMPLATE, SYSTEM_PROMPT


# ── Interface (Abstract Base Class) ────────────────────────────────────────────

class BaseOpenAIService(ABC):
    """Abstract base class for dharma recipe generation services."""

    @abstractmethod
    async def generate_dharma_recipe(
        self,
        mood: str,
        feelings: str = "",
        punya_context: str = "",
        breathing_context: str = "",
    ) -> Dict[str, Any]:
        """
        Generate a full spiritual recipe with 4 categories:
        gita, punya, breathing, reflections.
        """
        pass


# ── Production Service ─────────────────────────────────────────────────────────

class OpenAIService(BaseOpenAIService):
    """Production service using OpenAI API with guardrails."""

    def __init__(self, client: AsyncOpenAI) -> None:
        """Initialize with AsyncOpenAI client."""
        self.client = client

    async def generate_dharma_recipe(
        self,
        mood: str,
        feelings: str = "",
        punya_context: str = "",
        breathing_context: str = "",
    ) -> Dict[str, Any]:
        """Call OpenAI to generate a full dharma recipe."""
        feelings_line = f"The user adds: \"{feelings}\"" if feelings else ""

        user_prompt = RECIPE_PROMPT_TEMPLATE.format(
            mood=mood,
            feelings_line=feelings_line,
            punya_context=punya_context or "(No punya activities available in database yet.)",
            breathing_context=breathing_context or "(No breathing exercises available in database yet.)",
        )

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.6,
                max_tokens=800,
            )

            response_text = response.choices[0].message.content
            if not response_text:
                raise ValueError("OpenAI returned empty response")

            # Strip markdown code fences if present
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            recipe = json.loads(cleaned)
            _validate_recipe(recipe)
            return recipe

        except json.JSONDecodeError as e:
            raise ValueError(f"OpenAI response is not valid JSON: {e}") from e
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"OpenAI API call failed: {e}") from e


# ── Mock Service (Development) ─────────────────────────────────────────────────

class MockOpenAIService(BaseOpenAIService):
    """
    Mock service returning hardcoded dummy data (ENABLE_OPENAI=false).

    All text fields are suffixed with ' _DUMMY_' and the top-level
    response includes `"dummy_data": true` so the frontend / tests
    can detect that this is not real AI output.
    """

    async def generate_dharma_recipe(
        self,
        mood: str,
        feelings: str = "",
        punya_context: str = "",
        breathing_context: str = "",
    ) -> Dict[str, Any]:
        """Return mood-aware dummy recipe data."""
        return self._get_mock_recipe(mood)

    @staticmethod
    def _get_mock_recipe(mood: str) -> Dict[str, Any]:
        """Select mock recipe based on mood pattern matching."""
        mood_lower = mood.lower()

        # Pick chapter/verse and tone based on mood
        if any(w in mood_lower for w in ["anxious", "stress", "worry", "fear", "nervous"]):
            chapter, verse = 2, 47
            gita_title = "Release attachment to outcomes _DUMMY_"
            tone = "calming"
        elif any(w in mood_lower for w in ["sad", "depressed", "lost", "hopeless", "empty"]):
            chapter, verse = 10, 20
            gita_title = "You are never truly alone _DUMMY_"
            tone = "uplifting"
        elif any(w in mood_lower for w in ["grateful", "happy", "joyful", "peaceful", "content"]):
            chapter, verse = 12, 13
            gita_title = "Ground your joy in compassion _DUMMY_"
            tone = "grounding"
        elif any(w in mood_lower for w in ["angry", "frustrated", "resentful", "upset"]):
            chapter, verse = 2, 63
            gita_title = "Stillness between impulse and action _DUMMY_"
            tone = "soothing"
        elif any(w in mood_lower for w in ["confused", "uncertain", "unclear"]):
            chapter, verse = 2, 7
            gita_title = "Clarity comes from purposeful action _DUMMY_"
            tone = "clarifying"
        else:
            chapter, verse = 2, 15
            gita_title = "Both pleasure and pain are visitors _DUMMY_"
            tone = "balancing"

        return {
            "dummy_data": True,
            "gita": {
                "chapter": chapter,
                "verse_number": verse,
                "deeper_insights_title": gita_title,
                "deeper_insights": [
                    {
                        "emoji": "🕉️",
                        "title": f"Inner Steadiness _DUMMY_",
                        "inference": f"Focus on your duty without attachment to results — this {tone} insight is adapted to your mood _DUMMY_",
                    },
                    {
                        "emoji": "🌿",
                        "title": f"Present Moment _DUMMY_",
                        "inference": f"The mind finds peace when anchored in the present, not lost in what-ifs _DUMMY_",
                    },
                    {
                        "emoji": "✨",
                        "title": f"Eternal Self _DUMMY_",
                        "inference": f"Your true self is unchanging and untouched by temporary emotional waves _DUMMY_",
                    },
                ],
            },
            "punya": {
                "selected_number": 1,
                "why": f"Small acts of kindness release oxytocin and serotonin, grounding your {tone} state in service _DUMMY_",
                "impact": [
                    {
                        "emoji": "💛",
                        "point": "Triggers the helper's high — serotonin and dopamine flood your reward pathways _DUMMY_",
                    },
                    {
                        "emoji": "🌻",
                        "point": "Strengthens neural pathways associated with compassion and social bonding _DUMMY_",
                    },
                ],
            },
            "breathing": {
                "selected_number": 1,
                "why": f"Controlled breathing activates your vagus nerve, shifting you from fight-or-flight to calm _DUMMY_",
                "impact": [
                    {
                        "emoji": "🧘",
                        "point": "Heart rate variability improves within 90 seconds of slow breathing _DUMMY_",
                    },
                    {
                        "emoji": "🌊",
                        "point": "Cortisol levels drop as your parasympathetic nervous system activates _DUMMY_",
                    },
                ],
            },
            "reflections": [
                {
                    "emoji": "🪷",
                    "question": f"What is one thing within your control right now that deserves your full attention? _DUMMY_",
                },
                {
                    "emoji": "🌸",
                    "question": f"How might your perspective shift if you approached this moment with curiosity instead of judgment? _DUMMY_",
                },
                {
                    "emoji": "🙏",
                    "question": f"What would it feel like to release this weight and trust the process of your journey? _DUMMY_",
                },
            ],
        }


# ── Validation helper ──────────────────────────────────────────────────────────

def _validate_recipe(recipe: Dict[str, Any]) -> None:
    """Validate the structure of an AI-generated recipe response."""
    required_keys = {"gita", "punya", "breathing", "reflections"}
    if not required_keys.issubset(recipe.keys()):
        missing = required_keys - set(recipe.keys())
        raise ValueError(f"Missing required keys in AI response: {missing}")

    # Gita validation
    gita = recipe["gita"]
    if not isinstance(gita.get("chapter"), int) or not (1 <= gita["chapter"] <= 18):
        raise ValueError(f"Invalid gita.chapter: {gita.get('chapter')}")
    if not isinstance(gita.get("verse_number"), int) or gita["verse_number"] < 1:
        raise ValueError(f"Invalid gita.verse_number: {gita.get('verse_number')}")
    if not isinstance(gita.get("deeper_insights"), list) or len(gita["deeper_insights"]) != 3:
        raise ValueError("Expected exactly 3 gita.deeper_insights")

    # Punya validation
    punya = recipe["punya"]
    if not isinstance(punya.get("selected_number"), int):
        raise ValueError(f"Invalid punya.selected_number: {punya.get('selected_number')}")

    # Breathing validation
    breathing = recipe["breathing"]
    if not isinstance(breathing.get("selected_number"), int):
        raise ValueError(f"Invalid breathing.selected_number: {breathing.get('selected_number')}")

    # Reflections validation
    reflections = recipe["reflections"]
    if not isinstance(reflections, list) or len(reflections) != 3:
        raise ValueError("Expected exactly 3 reflections")


# ── Factory / Dependency Injection ─────────────────────────────────────────────

_openai_client: AsyncOpenAI | None = None
_openai_service: BaseOpenAIService | None = None


def get_openai_service() -> BaseOpenAIService:
    """
    Factory function returning appropriate service based on ENABLE_OPENAI flag.
    Returns either real OpenAI service or mock service.
    """
    global _openai_service
    if _openai_service is None:
        settings = get_settings()

        if settings.ENABLE_OPENAI:
            global _openai_client
            if _openai_client is None:
                _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            _openai_service = OpenAIService(_openai_client)
        else:
            _openai_service = MockOpenAIService()

    return _openai_service
