"""
app/models/ingredients.py
─────────────────────────
Polymorphic Beanie Document hierarchy for the `ingredients` collection.

Architecture:
  • BaseIngredient is the collection root (Settings.is_root = True).
    Beanie injects a `_class_id` discriminator field automatically so
    that all sub-types live in one collection but are deserialized into
    the correct Python class on retrieval.

  • Each concrete subclass corresponds to one ActivityType.  Using
    Literal[ActivityType.X] for the `activity_type` field gives:
      1. A typed default so the client never needs to set it explicitly.
      2. A queryable field for filtering (e.g., stories shuffle endpoint).
      3. A Pydantic discriminator for OpenAPI schema generation.

  • The `tags` field is a Dict[str, float] mapping semantic keywords to
    relevance scores. The AI engine uses these scores when matching
    ingredients to a user's mood (e.g., {"anxiety": 0.9, "stress": 0.8}).

  • The `why` field is the heart of Dharma AI's UX: a concise explanation
    grounding the practice in science or history rather than pure faith.
"""

from typing import Annotated, Dict, List, Literal, Optional
from enum import Enum
from datetime import datetime, timezone

from beanie import Document, Indexed
from pydantic import Field


# ── Enum ──────────────────────────────────────────────────────────────────────

class ActivityType(str, Enum):
    """
    Canonical set of spiritual ingredient categories.
    Synced to the frontend via GET /metadata/configs.
    """
    YOGA = "YOGA"
    GITA = "GITA"
    BREATHING = "BREATHING"
    MANTRA = "MANTRA"
    GOOD_DEED = "GOOD_DEED"
    STORY = "STORY"
    REFLECTION = "REFLECTION"


# ── Base (collection root) ────────────────────────────────────────────────────

class BaseIngredient(Document):
    """
    Polymorphic root for all spiritual ingredient types.

    This class is stored in the `ingredients` MongoDB collection.
    All subclasses inherit this schema and extend it with type-specific fields.
    Beanie uses the auto-injected `_class_id` field to round-trip documents
    back to the correct Python subclass.
    """

    # Polymorphic discriminator — concrete subclasses override with Literal.
    activity_type: ActivityType

    # ── Common content fields ─────────────────────────────────────────────────
    title: str = Field(..., description="Short, human-readable title.")
    why: str = Field(
        ...,
        description=(
            "The scientific or historical rationale for this practice. "
            "This is the core of Dharma AI's skeptic-friendly approach."
        ),
    )

    # ── AI matching metadata ──────────────────────────────────────────────────
    tags: Dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Semantic keyword → relevance score mapping used by the AI engine "
            "to match ingredients to a user's mood. "
            "Example: {'anxiety': 0.9, 'stress': 0.85, 'focus': 0.3}"
        ),
    )

    # ── Media ─────────────────────────────────────────────────────────────────
    icon_url: str = Field(
        default="",
        description="Azure Blob Storage URL for the category icon.",
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the ingredient was created (UTC).",
    )

    class Settings:
        name = "ingredients"
        is_root = True   # ← enables polymorphic inheritance in Beanie


# ── Concrete Subclasses ───────────────────────────────────────────────────────

class GitaVerse(BaseIngredient):
    """
    A verse from the Bhagavad Gita with multi-layer translations.

    Historical context: The Gita (c. 200 BCE – 200 CE) is a 700-verse
    philosophical poem embedded in the Mahabharata.  Modern psychology
    (Cognitive Behavioural Therapy, Stoicism) closely mirrors many of
    its frameworks for dealing with anxiety and inaction.
    """

    activity_type: Literal[ActivityType.GITA] = ActivityType.GITA

    # ── Verse identification ──────────────────────────────────────────────────
    chapter: Optional[int] = Field(
        default=None,
        description="Bhagavad Gita chapter number (1-18).",
    )
    verse_number: Optional[int] = Field(
        default=None,
        description="Verse number within the chapter.",
    )

    # ── Mood-adaptive inferences ──────────────────────────────────────────────
    inferences: List[str] = Field(
        default_factory=list,
        description=(
            "3 key insights derived from this verse, adapted to the user's mood. "
            "If user is sad/anxious, inferences are uplifting. "
            "If user is happy, inferences are grounding. "
            "AI-generated at request time, not stored in DB."
        ),
    )

    # ── Sanskrit layers ───────────────────────────────────────────────────────
    sanskrit_text: Optional[str] = Field(
        default=None,
        description="Original Devanagari script.",
    )
    transliteration: Optional[str] = Field(
        default=None,
        description="Roman-script phonetic rendering.",
    )
    english_translation: Optional[str] = Field(
        default=None,
        description="Literal English translation.",
    )
    commentary: Optional[str] = Field(
        default=None,
        description="Contextual commentary linking the verse to modern life.",
    )
    audio_url: str = Field(
        default="",
        description="Azure Blob URL for the verse recitation audio.",
    )


class Yoga(BaseIngredient):
    """
    A yoga asana (posture) with scientific anatomical context.

    Historical note: Yoga postures as a physical practice (Hatha Yoga)
    emerged ~15th century CE.  Modern research supports benefits for
    cortisol reduction, flexibility, and parasympathetic activation.
    """

    activity_type: Literal[ActivityType.YOGA] = ActivityType.YOGA

    gif_url: str = Field(
        default="",
        description="Azure Blob URL for the animated GIF demonstrating the posture.",
    )
    steps: List[str] = Field(
        default_factory=list,
        description="Ordered list of step-by-step instructions.",
    )
    anatomical_focus: str = Field(
        default="",
        description=(
            "Primary muscle groups or body systems targeted by this asana. "
            "Example: 'Activates the parasympathetic nervous system via "
            "vagal stimulation; stretches the psoas muscle.'"
        ),
    )


class Breathing(BaseIngredient):
    """
    A pranayama (breath-control) technique.

    Scientific basis: Controlled breathing directly modulates heart-rate
    variability (HRV) and CO₂/O₂ balance, activating the vagus nerve
    and reducing cortisol.  Studies (Zaccaro et al., 2018) show
    measurable reductions in anxiety within minutes.
    """

    activity_type: Literal[ActivityType.BREATHING] = ActivityType.BREATHING

    audio_url: str = Field(
        default="",
        description="Azure Blob URL for a guided audio track.",
    )
    duration_seconds: int = Field(
        default=0,
        description="Recommended total practice duration in seconds.",
    )
    pattern: str = Field(
        default="",
        description=(
            "Inhale-Hold-Exhale-Hold counts.  Example: '4-7-8' means "
            "inhale 4 counts, hold 7, exhale 8."
        ),
    )


class Chanting(BaseIngredient):
    """
    A mantra or chanting practice.

    Scientific basis: Rhythmic chanting synchronises neural oscillations
    (gamma waves), and specific frequencies (e.g. 136.1 Hz for 'Om')
    have been shown to reduce limbic system arousal (Kumar et al., 2010).
    """

    activity_type: Literal[ActivityType.MANTRA] = ActivityType.MANTRA

    audio_url: str = Field(
        default="",
        description="Azure Blob URL for the chanting audio.",
    )
    mantra_text: str = Field(
        default="",
        description="The mantra in its original script + transliteration.",
    )
    frequency_hz: float = Field(
        default=0.0,
        description="Primary acoustic frequency of the mantra in Hz.",
    )


class GoodDeed(BaseIngredient):
    """
    A small, actionable act of kindness (Seva / service).

    Psychological basis: Prosocial behaviour triggers oxytocin and
    serotonin release ('helper's high'), validated by neuroscience
    studies (Post, 2005).  This grounds the ancient concept of Dharma
    in measurable well-being outcomes.
    """

    activity_type: Literal[ActivityType.GOOD_DEED] = ActivityType.GOOD_DEED

    task_description: str = Field(
        default="",
        description="Concrete, single-sentence action the user should take today.",
    )
    impact_logic: str = Field(
        default="",
        description=(
            "Short explanation of *why* this deed matters — connecting the "
            "action to neurochemical, social, or environmental outcomes."
        ),
    )


class Story(BaseIngredient):
    """
    A short story from Hindu scripture reframed with historical/scientific context.

    These serve as the primary 'edu-tainment' content layer of the app,
    designed to engage skeptics who may dismiss mythology as superstition.
    """

    activity_type: Literal[ActivityType.STORY] = ActivityType.STORY

    story_text: str = Field(
        default="",
        description="The narrative body of the story (Markdown supported).",
    )
    scripture_source: str = Field(
        default="",
        description=(
            "The scripture, text, or oral tradition the story originates from. "
            "Example: 'Rigveda 10.129 (Nasadiya Sukta), c. 1500 BCE'"
        ),
    )
    image_url: str = Field(
        default="",
        description="Azure Blob URL for the story's illustration.",
    )


class Reflection(BaseIngredient):
    """
    Therapist-style reflection questions generated by OpenAI.

    This ingredient contains 3 open-ended questions designed to encourage
    the user to reflect deeply on the selected Bhagavad Gita verse and
    how it relates to their current mood and situation.

    Design:
      • Companion to GitaVerse in the recipe response.
      • Generated at request time by OpenAI based on mood, feelings, and verse.
      • Purely text-based (no media, audio, or persistent storage in DB).
    """

    activity_type: Literal[ActivityType.REFLECTION] = ActivityType.REFLECTION

    reflection_questions: List[str] = Field(
        default_factory=list,
        description=(
            "3 open-ended, therapist-style questions for self-reflection. "
            "Each question encourages the user to introspect on the verse's "
            "relevance to their current mood and life situation."
        ),
    )
