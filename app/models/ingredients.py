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

  • Common optional fields (emoji, subtitle, duration_mins, context)
    live on BaseIngredient so every subclass inherits them.
    These are DB-stored and used for display + passing context to the AI.

  • The `context` field is a Dict[str, str] holding key-value metadata
    such as location (work/home/anywhere), time_of_day (day/night),
    and short_descp (brief AI context string).

  • The `ai_why` field is the heart of Dharma AI's UX: a concise explanation
    grounding the practice in science or history rather than pure faith.
"""

from typing import Dict, List, Literal, Optional
from enum import Enum
from datetime import datetime, timezone

from beanie import Document
from pydantic import BaseModel, Field


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
    PUNYA = "PUNYA"
    STORY = "STORY"
    REFLECTION = "REFLECTION"


# ── Embedded Pydantic models (used in AI-generated responses) ─────────────────

class DeeperInsight(BaseModel):
    """A single deeper insight for a Gita verse, with emoji and title."""
    emoji: str = Field(..., description="Safe, positive emoji for this insight.")
    title: str = Field(..., description="Short title for the insight.")
    inference: str = Field(
        ...,
        description="The insight text (~25 words), grounded in the verse and user mood.",
    )


class ImpactPointer(BaseModel):
    """A single impact pointer for PUNYA / BREATHING activities."""
    emoji: str = Field(..., description="Safe, positive emoji.")
    point: str = Field(..., description="Impact statement (~20 words).")


class ReflectionQuestion(BaseModel):
    """A therapist-style reflection question with emoji."""
    emoji: str = Field(..., description="Safe, positive emoji for the question.")
    question: str = Field(..., description="Open-ended self-reflection question.")


class BreathPhase(BaseModel):
    """A single phase in a breathing cycle (e.g. INHALE for 4 seconds)."""
    name: str = Field(..., description="Phase name: INHALE, HOLD, EXHALE.")
    seconds: int = Field(..., description="Duration of this phase in seconds.")
    instruction: str = Field(default="", description="User-facing guidance for this phase.")


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
    emoji: str = Field(
        default="",
        description="Decorative emoji for this ingredient (safe, positive only).",
    )
    subtitle: str = Field(
        default="",
        description="Secondary display text shown below the title.",
    )
    ai_why: Optional[str] = Field(
        default="",
        description=(
            "The scientific or historical rationale for this practice. "
            "This is the core of Dharma AI's skeptic-friendly approach. "
            "AI-generated at response time for personalised context."
        ),
    )
    duration_mins: Optional[int] = Field(
        default=None,
        description="Read or practice duration in minutes.",
    )
    context: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Key-value context pairs for this activity. "
            "Standard keys: 'location', 'time_of_day', 'short_descp'. "
            "Example: {'location': 'work', 'time_of_day': 'day', "
            "'short_descp': 'Alternate nostril breathing to reduce anxiety'}"
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

    DB-stored: chapter, verse_number, sanskrit_text, english_translation,
    commentary, audio_url.
    AI-generated at runtime: deeper_insights_title, deeper_insights (3 items).
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

    # ── AI-generated deeper insights (set at response time, not stored) ───────
    deeper_insights_title: Optional[str] = Field(
        default=None,
        description=(
            "One short evocative line summarising the deeper insight theme. "
            "E.g. 'The ocean doesn't ask the river to stop'. AI-generated."
        ),
    )
    deeper_insights: List[DeeperInsight] = Field(
        default_factory=list,
        description=(
            "3 deeper insights, each with emoji + title + inference (~25 words). "
            "Adapted to user mood: uplifting if sad, grounding if happy. "
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

    DB-stored: audio_url, duration_seconds, animation, breath_phases, cycles, steps.
    AI-generated at runtime: ai_why, ai_impact (1-3 pointers).
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
    animation: str = Field(
        default="",
        description=(
            "Frontend animation style. "
            "Values: hold-pulse, vibrate, asymmetric, pulse, rapid."
        ),
    )
    breath_phases: List[BreathPhase] = Field(
        default_factory=list,
        description=(
            "Ordered list of phases in one breathing cycle. "
            "Each phase has a name, duration in seconds, and instruction."
        ),
    )
    cycles: int = Field(
        default=0,
        description="Number of times to repeat the breath_phases cycle.",
    )
    steps: List[str] = Field(
        default_factory=list,
        description="Step-by-step textual instructions for the technique.",
    )

    # ── AI-generated fields (set at response time, not stored in DB) ──────────
    ai_impact: Optional[List[ImpactPointer]] = Field(
        default=None,
        description=(
            "1-3 impact pointers (each ~20 words with emoji) describing "
            "how the user feels after completing the exercise. AI-generated."
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


class Punya(BaseIngredient):
    """
    A small, actionable act of kindness / good deed (Seva / Punya).

    Psychological basis: Prosocial behaviour triggers oxytocin and
    serotonin release ('helper's high'), validated by neuroscience
    studies (Post, 2005).  This grounds the ancient concept of Dharma
    in measurable well-being outcomes.

    DB-stored: activity (what to do), context.
    AI-generated at runtime: ai_why, ai_impact (1-3 pointers).
    """

    activity_type: Literal[ActivityType.PUNYA] = ActivityType.PUNYA

    activity: str = Field(
        default="",
        description="Concrete, single-sentence action the user should take today.",
    )

    # ── AI-generated fields (set at response time, not stored in DB) ──────────
    ai_impact: Optional[List[ImpactPointer]] = Field(
        default=None,
        description=(
            "1-3 impact pointers (each ~20 words with emoji) describing "
            "the rewiring/rejuvenation effect after doing this activity. AI-generated."
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

    Contains 3 open-ended questions (each with an emoji) designed to
    encourage the user to pause, think, and reflect on the selected
    Gita verse and suggested activities in relation to their mood.

    Design:
      • Companion to GitaVerse, Punya, and Breathing in the recipe response.
      • Generated at request time by OpenAI based on mood, feelings, and
        all suggested activities.
      • Purely text-based (no media, audio, or persistent storage in DB).
    """

    activity_type: Literal[ActivityType.REFLECTION] = ActivityType.REFLECTION

    reflection_questions: List[ReflectionQuestion] = Field(
        default_factory=list,
        description=(
            "3 open-ended, therapist-style questions for self-reflection. "
            "Each has an emoji and a question that encourages introspection "
            "on the verse's relevance to the user's current mood and life."
        ),
    )
