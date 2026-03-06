"""
app/services/ai_service.py
───────────────────────────
AI Engine Strategy Pattern for the /recipe endpoint.

Architecture:
  AIEngine is an Abstract Base Class (ABC) defining the interface.
  Concrete implementations are swapped in via FastAPI's Depends()
  without touching a single line of route code.

  Current implementations:
    • MockAIEngine  – Returns one ingredient per ActivityType from the DB.
                      Used in all local development and CI pipelines.

  Planned implementations:
    • ClaudeAIEngine – Calls Anthropic Claude with mood+feelings as context,
                       uses structured output to select ingredient ObjectIds,
                       then fetches those documents from MongoDB.

Swap guide:
  1. Create a new class that inherits AIEngine.
  2. Implement `generate_recipe`.
  3. In app/api/dependencies.py, change `get_ai_engine` to return your class.
  Zero changes required to app/api/routes/recipe.py.
"""

from abc import ABC, abstractmethod
from typing import List

from app.models.ingredients import ActivityType, BaseIngredient


class AIEngine(ABC):
    """
    Abstract contract for all AI recipe generation strategies.

    generate_recipe must be an async method because all implementations
    are expected to perform I/O (DB queries, HTTP calls to an LLM API).
    """

    @abstractmethod
    async def generate_recipe(
        self,
        mood: str,
        feelings: str,
    ) -> List[BaseIngredient]:
        """
        Generate a personalized list of spiritual 'ingredients' (activities).

        Args:
            mood:     A short keyword describing the user's emotional state.
                      Example: "anxious", "grateful", "lost"
            feelings: Free-form text from the user elaborating on their state.
                      Example: "I can't stop overthinking work deadlines."

        Returns:
            A heterogeneous list of BaseIngredient subclass instances.
            Each element may be a GitaVerse, Yoga, Breathing, Chanting,
            Punya, or Story document.
        """
        raise NotImplementedError


class MockAIEngine(AIEngine):
    """
    Development-stage implementation that returns one ingredient per
    ActivityType from the database, ignoring mood/feelings entirely.

    Behaviour:
      • Iterates over every ActivityType enum value.
      • For each type, fetches the first matching document in the DB.
      • Skips types for which no data exists yet (graceful degradation).

    This means the /recipe endpoint works end-to-end in local dev as
    long as the database has been seeded (see scripts/seed_data.py).
    """

    async def generate_recipe(
        self,
        mood: str,
        feelings: str,
    ) -> List[BaseIngredient]:
        """
        Returns a fixed-order recipe: one of each ingredient type.
        Order: YOGA → BREATHING → GITA → MANTRA → PUNYA → STORY
        """
        recipe: List[BaseIngredient] = []

        # Preferred display order for a well-rounded daily recipe.
        ordered_types = [
            ActivityType.YOGA,
            ActivityType.BREATHING,
            ActivityType.GITA,
            ActivityType.MANTRA,
            ActivityType.PUNYA,
            ActivityType.STORY,
        ]

        for activity_type in ordered_types:
            ingredient = await BaseIngredient.find_one(
                BaseIngredient.activity_type == activity_type,
            )
            if ingredient is not None:
                recipe.append(ingredient)

        return recipe


# ── Future implementation stub ─────────────────────────────────────────────────
# Uncomment and complete when integrating with the Anthropic API.
#
# from anthropic import AsyncAnthropic
#
# class ClaudeAIEngine(AIEngine):
#     """
#     Production AI engine powered by Anthropic Claude.
#
#     Strategy:
#       1. Build a system prompt describing the ingredient catalog schema.
#       2. Send the user's mood + feelings as the human turn.
#       3. Ask Claude (with structured output / tool_use) to return a JSON
#          list of MongoDB ObjectIds best suited to the user's state.
#       4. Fetch those documents from MongoDB and return them.
#     """
#
#     def __init__(self) -> None:
#         self._client = AsyncAnthropic()
#
#     async def generate_recipe(self, mood: str, feelings: str) -> List[BaseIngredient]:
#         ...  # Implementation goes here
