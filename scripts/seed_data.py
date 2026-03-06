"""
scripts/seed_data.py
─────────────────────
Populates the local development database with sample data so that all
API endpoints work out-of-the-box without manual data entry.

Seeds:
  • One ingredient document of every ActivityType
    (GitaVerse, Yoga, Breathing, Chanting, Punya, Story)
  • DailyPanchang entries for Mumbai and Delhi for the next 7 days

Usage (from the project root):
  # With docker-compose running:
  docker-compose exec api python -m scripts.seed_data

  # Or directly against a local MongoDB:
  MONGODB_URL=mongodb://localhost:27017 python -m scripts.seed_data

Important: Beanie Document instances can only be constructed AFTER
init_beanie() is called.  All sample data is therefore built inside
the seed() coroutine, not at module level.
"""

import asyncio
import os
from datetime import date, timedelta

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.models.ingredients import (
    BaseIngredient,
    Breathing,
    Chanting,
    GitaVerse,
    Punya,
    Story,
    Yoga,
)
from app.models.panchang import DailyPanchang
from app.models.user import User


# ── Sample ingredient builders ────────────────────────────────────────────────
# Each is a plain function (not a module-level constant) so Beanie's
# collection is guaranteed to be initialised before instantiation.

def _gita_verse() -> GitaVerse:
    return GitaVerse(
        title="Bhagavad Gita 2.47 — On Action Without Attachment",
        emoji="📖",
        subtitle="Karmanye vadhikaraste",
        duration_mins=5,
        chapter=2,
        verse_number=47,
        why=(
            "Modern psychology calls this 'process focus' versus 'outcome focus'. "
            "Research (Dweck, 2006) shows that process-focused individuals exhibit "
            "higher resilience and sustained motivation compared to those fixated on results."
        ),
        tags={"anxious": 0.9, "lost": 0.85, "stress": 0.8, "focus": 0.7},
        icon_url="",
        sanskrit_text="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
        transliteration="Karmanye vadhikaraste Ma Phaleshu Kadachana",
        english_translation=(
            "You have a right to perform your prescribed duty, "
            "but you are not entitled to the fruits of action."
        ),
        commentary=(
            "Krishna instructs Arjuna to act with full dedication while releasing "
            "attachment to outcomes.  This maps directly to Acceptance and Commitment "
            "Therapy (ACT): engage fully with the process, accept uncertainty about results.  "
            "Neurologically, outcome-fixation activates the amygdala (fear response), "
            "while process-focus engages the prefrontal cortex (clarity and planning)."
        ),
        audio_url="",
    )


def _yoga() -> Yoga:
    return Yoga(
        title="Balasana — Child's Pose",
        why=(
            "Balasana activates the parasympathetic nervous system by stimulating "
            "the vagus nerve through mild thoracic compression.  Studies show a "
            "measurable drop in cortisol within 90 seconds of holding the pose "
            "(Streeter et al., 2012, Journal of Alternative and Complementary Medicine)."
        ),
        tags={"anxious": 0.95, "stress": 0.9, "angry": 0.7, "tired": 0.6},
        icon_url="",
        gif_url="",
        steps=[
            "Kneel on the floor with your big toes touching and knees hip-width apart.",
            "Sit back on your heels and exhale as you fold forward.",
            "Extend your arms forward or rest them alongside your body.",
            "Rest your forehead on the mat.  Breathe slowly and deeply.",
            "Hold for 1–3 minutes, focusing on the sensation of your ribs expanding.",
        ],
        anatomical_focus=(
            "Stretches: lumbar erector spinae, gluteus maximus, hip rotators.  "
            "Activates: vagus nerve (thoracic branch), parasympathetic nervous system.  "
            "Compresses: adrenal glands — promoting cortisol regulation."
        ),
    )


def _breathing() -> Breathing:
    return Breathing(
        title="Nadi Shodhana — Alternate Nostril Breathing",
        emoji="🧘",
        subtitle="Balance your hemispheres",
        duration_mins=5,
        location="anywhere",
        short_descp="Alternate nostril breathing to balance brain hemispheres and reduce anxiety",
        why=(
            "Alternating nostril breathing balances activity between the left "
            "(parasympathetic) and right (sympathetic) hemispheres of the brain.  "
            "EEG studies (Telles et al., 1994) demonstrate increased alpha-wave "
            "activity and subjective calmness within 5 minutes of practice.  "
            "The technique also increases blood oxygen saturation by ~2–3%."
        ),
        tags={"anxious": 0.92, "stress": 0.88, "angry": 0.75, "lost": 0.6},
        icon_url="",
        audio_url="",
        duration_seconds=300,
        pattern="4-0-4-0",
        animation=1,
    )


def _chanting() -> Chanting:
    return Chanting(
        title="Om Chanting — The Primordial Sound",
        why=(
            "The syllable 'Om' (AUM) chanted at ~136.1 Hz creates standing resonance "
            "in the cranial vault.  fMRI studies (Kalyani et al., 2011) show deactivation "
            "of the limbic system (fear/anger centre) during Om chanting — a response "
            "similar to that of anti-anxiety medication, but drug-free."
        ),
        tags={"anxious": 0.88, "peaceful": 0.95, "curious": 0.6, "grateful": 0.7},
        icon_url="",
        audio_url="",
        mantra_text="ॐ (Om / AUM)",
        frequency_hz=136.1,
    )


def _punya() -> Punya:
    return Punya(
        title="Pay for a stranger's chai",
        emoji="🌻",
        subtitle="A small act of kindness",
        duration_mins=5,
        location="anywhere",
        short_descp="Pay for a stranger's tea or donate a small amount via UPI",
        activity=(
            "Next time you're at a tea stall or cafe, pay for the person behind you. "
            "If you're working from home, transfer ₹20 to a local street vendor via UPI."
        ),
        why=(
            "Prosocial spending — spending money on others rather than yourself — "
            "activates the nucleus accumbens (reward centre) more strongly than "
            "self-directed spending (Dunn et al., 2008, Science).  "
            "Even a small act triggers an oxytocin release cycle, improving your "
            "own mood for up to 2 hours post-action."
        ),
        tags={"sad": 0.9, "lost": 0.8, "grateful": 0.85, "angry": 0.6},
        icon_url="",
    )


def _story() -> Story:
    return Story(
        title="The Churning of the Ocean — The First Collaboration",
        why=(
            "The Samudra Manthan allegory (c. 1500 BCE, Vishnu Purana) describes "
            "opposing forces (gods and demons) cooperating to extract value from chaos.  "
            "Modern organisational psychology echoes this: diverse, even adversarial, "
            "teams consistently outperform homogeneous ones on complex problems "
            "(Page, 2007, 'The Difference')."
        ),
        tags={"lost": 0.85, "curious": 0.9, "angry": 0.7, "anxious": 0.65},
        icon_url="",
        story_text=(
            "Long ago, the gods (Devas) were losing their power.  Vishnu advised them "
            "to churn the cosmic ocean of milk to recover Amrita, the nectar of immortality.\n\n"
            "There was one problem: the task was too vast for either side alone.  "
            "The Devas made a pact with their eternal rivals, the Asuras.  They used "
            "Mount Mandara as a churning rod and the serpent Vasuki as the rope.\n\n"
            "The churning was violent.  First came Halahala — a poison so potent it "
            "threatened to destroy creation.  Shiva stepped forward and drank it, "
            "holding it in his throat (turning it blue) to save the world.\n\n"
            "After immense labour, Amrita emerged — along with Lakshmi, Dhanvantari "
            "(physician of the gods), and 14 other treasures.\n\n"
            "**The modern lens:** The ocean is your mind.  Churning — sustained, "
            "uncomfortable effort — is required before anything of value surfaces.  "
            "The poison that appears first?  That's the discomfort you must sit with "
            "before the insight arrives."
        ),
        scripture_source=(
            "Vishnu Purana, Book 1, Chapter 9; "
            "also Bhagavata Purana, Skanda 8 (c. 400–1000 CE)"
        ),
        image_url="",
    )


# ── Panchang builder ──────────────────────────────────────────────────────────

def _panchang_entries() -> list[DailyPanchang]:
    """Generates 7 days of mock Panchang entries for Mumbai and Delhi."""
    tithis = [
        ("Pratipada", "06:30"), ("Dwitiya", "07:15"), ("Tritiya", "08:00"),
        ("Chaturthi", "09:45"), ("Panchami", "11:30"), ("Shashthi", "13:15"),
        ("Saptami", "15:00"),
    ]
    nakshatras = [
        ("Ashwini", "08:45"), ("Bharani", "09:30"), ("Krittika", "10:15"),
        ("Rohini", "11:00"), ("Mrigashira", "12:45"), ("Ardra", "14:30"),
        ("Punarvasu", "16:15"),
    ]
    yogas = ["Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti"]
    karanas = [("Bava", "18:00"), ("Balava", "06:00"), ("Kaulava", "18:30")]
    inferences_pool = [
        [
            "Shukla Paksha (waxing moon phase) correlates with rising melatonin "
            "sensitivity — consider earlier bedtimes.",
            "Lunar gravitational pull is increasing; coastal residents may notice "
            "higher-than-average tides today.",
        ],
        [
            "Rohini Nakshatra historically associated with fertile agricultural "
            "periods — early botanists noted increased plant transpiration during "
            "this lunar transit.",
        ],
        [
            "Purnamasi (Full Moon) proximity: studies report a ~23-minute reduction "
            "in average sleep duration in the 3–5 days around a full moon "
            "(Cajochen et al., 2013, Current Biology).",
        ],
    ]
    vaars = ["Ravivaar", "Somavaar", "Mangalavaar", "Budhavaar",
             "Guruvaar", "Shukravaar", "Shanivaar"]

    entries: list[DailyPanchang] = []
    today = date.today()

    for i in range(7):
        target_date = today + timedelta(days=i)
        tithi, tithi_end = tithis[i % len(tithis)]
        nakshatra, nakshatra_end = nakshatras[i % len(nakshatras)]
        karana, karana_end = karanas[i % len(karanas)]

        for city in ("Mumbai", "Delhi"):
            entries.append(DailyPanchang(
                date=target_date,
                city=city,
                tithi=tithi,
                tithi_end=tithi_end,
                nakshatra=nakshatra,
                nakshatra_end=nakshatra_end,
                vaar=vaars[target_date.weekday()],
                yoga=yogas[i % len(yogas)],
                karana=karana,
                karana_end=karana_end,
                paksha="Shukla Paksha" if i < 15 else "Krishna Paksha",
                inferences=inferences_pool[i % len(inferences_pool)],
            ))

    return entries


# ── Main ──────────────────────────────────────────────────────────────────────

async def seed() -> None:
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "dharma_db")

    client: AsyncIOMotorClient = AsyncIOMotorClient(mongodb_url)
    await init_beanie(
        database=client[database_name],
        document_models=[
            User,
            BaseIngredient,
            GitaVerse,
            Yoga,
            Breathing,
            Chanting,
            Punya,
            Story,
            DailyPanchang,
        ],
    )

    # ── Ingredients ───────────────────────────────────────────────────────────
    print("Seeding ingredients...")
    for builder in [_gita_verse, _yoga, _breathing, _chanting, _punya, _story]:
        ingredient = builder()
        existing = await BaseIngredient.find_one(
            BaseIngredient.activity_type == ingredient.activity_type,
        )
        if existing is None:
            await ingredient.insert()
            print(f"  + Inserted {ingredient.activity_type.value}: {ingredient.title}")
        else:
            print(f"  - Skipped  {ingredient.activity_type.value} (already exists)")

    # ── Panchang ──────────────────────────────────────────────────────────────
    print("\nSeeding Panchang data (7 days x 2 cities)...")
    for entry in _panchang_entries():
        existing = await DailyPanchang.find_one(
            DailyPanchang.city == entry.city,
            DailyPanchang.date == entry.date,
        )
        if existing is None:
            await entry.insert()
            print(f"  + Inserted {entry.city} / {entry.date}")
        else:
            print(f"  - Skipped  {entry.city} / {entry.date} (already exists)")

    print("\nSeed complete.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
