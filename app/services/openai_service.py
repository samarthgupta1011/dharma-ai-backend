"""
app/services/openai_service.py
──────────────────────────────
Service for generating Bhagavad Gita verse recommendations and psychological reflections
using OpenAI's API (GPT-4o-mini) or mock data.

Architecture:
  • `BaseOpenAIService`: Abstract base class defining the interface
  • `OpenAIService`: Production class making real OpenAI API calls
  • `MockOpenAIService`: Development class returning hardcoded mock data (no API call)
  • `get_openai_service()`: Factory that returns appropriate service based on ENABLE_OPENAI flag

Design decisions:
  • Uses strategy pattern for transparent switching between real and mock implementations
  • Mock service has identical interface, so calling code doesn't change
  • Async/await with httpx to avoid blocking the event loop (real service only)
  • Singleton per-process instance with a single OpenAI client
  • Errors are descriptive and include guidance for debugging
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict

from openai import AsyncOpenAI

from app.config.settings import get_settings


# ── Interface (Abstract Base Class) ────────────────────────────────────────────

class BaseOpenAIService(ABC):
    """Abstract base class for Gita guidance services."""

    @abstractmethod
    async def generate_gita_guidance(
        self,
        mood: str,
        feelings: str = "",
    ) -> Dict[str, Any]:
        """Generate Gita verse recommendation with inferences and reflection questions."""
        pass


# ── Production Service ─────────────────────────────────────────────────────────

class OpenAIService(BaseOpenAIService):
    """Production service using OpenAI API."""

    def __init__(self, client: AsyncOpenAI) -> None:
        """Initialize with AsyncOpenAI client."""
        self.client = client

    async def generate_gita_guidance(
        self,
        mood: str,
        feelings: str = "",
    ) -> Dict[str, Any]:
        """Call OpenAI to generate Gita guidance."""
        feelings_str = f" User detail: {feelings}" if feelings else ""
        prompt = f"""User mood: {mood}.{feelings_str}

Recommend ONE Gita verse (ch.verse, e.g., 4.24 from chapters 1-18).

Return JSON:
{{
  "chapter": <int>,
  "verse_number": <int>,
  "inferences": [<3 insights adapted to mood: uplifting if sad, grounding if happy>],
  "reflection_questions": [<3 open-ended self-reflection questions>]
}}

Example:
{{
  "chapter": 2,
  "verse_number": 47,
  "inferences": ["Your duty is the action; not attached to fruit.", "Trust the process.", "Anxiety dissolves with focus on effort."],
  "reflection_questions": ["What's in your control?", "How would releasing outcomes help?", "What becomes possible by trusting?"]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )

            response_text = response.choices[0].message.content
            if not response_text:
                raise ValueError("OpenAI returned empty response")

            guidance = json.loads(response_text)

            # Validate response structure
            required_keys = {"chapter", "verse_number", "inferences", "reflection_questions"}
            if not required_keys.issubset(guidance.keys()):
                raise ValueError(f"Missing required keys in OpenAI response")

            if not isinstance(guidance["chapter"], int) or not (1 <= guidance["chapter"] <= 18):
                raise ValueError(f"Invalid chapter: {guidance['chapter']}")

            if not isinstance(guidance["verse_number"], int) or guidance["verse_number"] < 1:
                raise ValueError(f"Invalid verse_number: {guidance['verse_number']}")

            if not isinstance(guidance["inferences"], list) or len(guidance["inferences"]) != 3:
                raise ValueError(f"Expected 3 inferences")

            if not isinstance(guidance["reflection_questions"], list) or len(guidance["reflection_questions"]) != 3:
                raise ValueError(f"Expected 3 reflection questions")

            return guidance

        except json.JSONDecodeError as e:
            raise ValueError(f"OpenAI response is not valid JSON: {e}") from e
        except Exception as e:
            raise ValueError(f"OpenAI API call failed: {e}") from e


# ── Mock Service (Development) ─────────────────────────────────────────────────

class MockOpenAIService(BaseOpenAIService):
    """Mock service returning hardcoded data (ENABLE_OPENAI=false)."""

    async def generate_gita_guidance(
        self,
        mood: str,
        feelings: str = "",
    ) -> Dict[str, Any]:
        """Return mock guidance data based on mood."""
        return self._get_mock_guidance(mood)

    @staticmethod
    def _get_mock_guidance(mood: str) -> Dict[str, Any]:
        """Select mock guidance based on mood pattern matching."""
        mood_lower = mood.lower()

        if any(word in mood_lower for word in ["anxious", "stress", "worry", "fear", "nervous"]):
            return {
                "chapter": 2,
                "verse_number": 47,
                "inferences": [
                    "Your only right is to perform your duty; the fruits of action are not your concern.",
                    "Let go of attachment to outcomes and focus on the quality of effort.",
                    "This mindset transforms anxiety into purposeful, grounded action.",
                ],
                "reflection_questions": [
                    "What actions are truly within your control right now?",
                    "How might your anxiety shift if you focused only on the process, not the result?",
                    "What would become possible if you trusted the unfolding of your path?",
                ],
            }

        elif any(word in mood_lower for word in ["sad", "depressed", "lost", "hopeless", "empty"]):
            return {
                "chapter": 10,
                "verse_number": 20,
                "inferences": [
                    "I am the self within all beings; you are never truly isolated.",
                    "Your essence is eternal and unchanging despite temporary sorrows.",
                    "This recognition transforms despair into a sense of belonging.",
                ],
                "reflection_questions": [
                    "What part of you remains untouched by this sadness?",
                    "How might you connect with something larger than this moment?",
                    "What light persists within you, even now?",
                ],
            }

        elif any(word in mood_lower for word in ["grateful", "happy", "joyful", "peaceful", "content"]):
            return {
                "chapter": 12,
                "verse_number": 13,
                "inferences": [
                    "Ground your joy in compassion and service, not circumstance.",
                    "Equanimity deepens happiness—holding it lightly, sharing it freely.",
                    "This stability prevents joy from turning into attachment or fear of loss.",
                ],
                "reflection_questions": [
                    "How can you share or ground this happiness in service?",
                    "What would it mean to hold this joy without grasping?",
                    "How might you deepen this peace through compassion for others?",
                ],
            }

        elif any(word in mood_lower for word in ["confused", "uncertain", "lost", "unclear"]):
            return {
                "chapter": 2,
                "verse_number": 7,
                "inferences": [
                    "Clarity comes from engaged action with full awareness, not endless thinking.",
                    "Confusion dissolves when you align intention with purposeful effort.",
                    "Trust that moving forward with integrity reveals the path ahead.",
                ],
                "reflection_questions": [
                    "What is one small, clear action you can take today?",
                    "How might taking aligned action clarify your direction?",
                    "What part of this situation needs your presence, not your planning?",
                ],
            }

        elif any(word in mood_lower for word in ["angry", "frustrated", "resentful", "upset"]):
            return {
                "chapter": 2,
                "verse_number": 63,
                "inferences": [
                    "Anger clouds judgment; observe it without acting from it.",
                    "The gap between impulse and action is where wisdom lives.",
                    "Breathe, pause, and respond from your higher self, not reaction.",
                ],
                "reflection_questions": [
                    "What legitimate need or boundary is your anger protecting?",
                    "How might you honor that need without destructive action?",
                    "What would responding from clarity, not anger, look like?",
                ],
            }

        else:
            return {
                "chapter": 2,
                "verse_number": 15,
                "inferences": [
                    "Both pleasure and pain are temporary visitors; neither defines you.",
                    "Witness your emotions without being swept away by them.",
                    "This inner steadiness is your natural state, beneath the storm.",
                ],
                "reflection_questions": [
                    "What in you is unchanged by your current emotions?",
                    "How can you observe your feelings with kindness and distance?",
                    "What steadiness or peace are you cultivating within?",
                ],
            }


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
