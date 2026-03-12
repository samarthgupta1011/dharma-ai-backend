"""
scripts/seed_recipe_data.py
────────────────────────────
Populates the database with 15 recipe-ready ingredients:
  • 5 GitaVerse  (matched to the mock service's mood→verse mapping)
  • 5 Punya      (diverse real-world acts of kindness)
  • 5 Breathing   (classic pranayama techniques)

This ensures the recipe API works fully in both modes:
  • ENABLE_OPENAI=false  → mock picks selected_number=1, DB supplies real fields
  • ENABLE_OPENAI=true   → AI picks from numbered context list, DB supplies real fields

Usage:
  # Local (docker-compose running):
  docker-compose exec api python -m scripts.seed_recipe_data

  # Against any MongoDB / Cosmos DB:
  MONGODB_URL="<connection-string>" DATABASE_NAME="dharma_db" python -m scripts.seed_recipe_data

Idempotent: skips documents that already exist (by chapter+verse for Gita, title for others).
"""

import asyncio
import os

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.models.ingredients import (
    BaseIngredient,
    BreathPhase,
    Breathing,
    GitaVerse,
    Punya,
)
from app.models.user import User
from app.models.panchang import DailyPanchang
from app.models.recipe_request import RecipeRequest


# ── Gita Verses ───────────────────────────────────────────────────────────────

def _gita_verses() -> list[GitaVerse]:
    return [
        # 1 — BG 2.47: anxious / stress / focus
        GitaVerse(
            title="Bhagavad Gita 2.47 — On Action Without Attachment",
            emoji="📖",
            subtitle="Karmanye vadhikaraste",
            duration_mins=5,
            chapter=2,
            verse_number=47,
            context={"location": "anywhere", "short_descp": "Chapter 2, Verse 47"},
            ai_why=(
                "Modern psychology calls this 'process focus' versus 'outcome focus'. "
                "Research (Dweck, 2006) shows that process-focused individuals exhibit "
                "higher resilience and sustained motivation compared to those fixated on results."
            ),
            sanskrit_text="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन। मा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
            transliteration=(
                "Karmanye vadhikaraste Ma Phaleshu Kadachana, "
                "Ma Karmaphalaheturbhurma Te Sangostvakarmani"
            ),
            english_translation=(
                "You have a right to perform your prescribed duty, "
                "but you are not entitled to the fruits of action. "
                "Never consider yourself the cause of the results of your activities, "
                "and never be attached to not doing your duty."
            ),
            commentary=(
                "Krishna instructs Arjuna to act with full dedication while releasing "
                "attachment to outcomes. This maps directly to Acceptance and Commitment "
                "Therapy (ACT): engage fully with the process, accept uncertainty about results. "
                "Neurologically, outcome-fixation activates the amygdala (fear response), "
                "while process-focus engages the prefrontal cortex (clarity and planning)."
            ),
            audio_url="",
            icon_url="",
        ),
        # 2 — BG 10.20: low / sad / lonely
        GitaVerse(
            title="Bhagavad Gita 10.20 — The Divine Dwells Within All",
            emoji="🙏",
            subtitle="Aham atma gudakesha",
            duration_mins=5,
            chapter=10,
            verse_number=20,
            context={"location": "anywhere", "short_descp": "Chapter 10, Verse 20"},
            ai_why=(
                "Neuroscience shows that feelings of isolation trigger the same brain regions "
                "as physical pain (Eisenberger, 2012). This verse reframes aloneness — "
                "the divine is seated in every heart, which aligns with modern attachment "
                "theory: a sense of 'secure base' reduces cortisol and anxiety."
            ),
            sanskrit_text="अहमात्मा गुडाकेश सर्वभूताशयस्थितः। अहमादिश्च मध्यं च भूतानामन्त एव च॥",
            transliteration=(
                "Aham atma gudakesha sarva-bhutashaya-sthitah, "
                "aham adish cha madhyam cha bhutanam anta eva cha"
            ),
            english_translation=(
                "I am the Self, O Gudakesha (Arjuna), seated in the hearts of all creatures. "
                "I am the beginning, the middle, and the end of all beings."
            ),
            commentary=(
                "Krishna reveals that the divine consciousness is not distant or abstract — "
                "it resides within every living being. Modern positive psychology echoes this: "
                "the practice of recognising shared humanity (Neff, 2011) significantly reduces "
                "feelings of isolation and increases self-compassion."
            ),
            audio_url="",
            icon_url="",
        ),
        # 3 — BG 6.35: scattered / restless / distracted
        GitaVerse(
            title="Bhagavad Gita 6.35 — Mastering the Restless Mind",
            emoji="🧘",
            subtitle="Asanshayam mahabaho",
            duration_mins=5,
            chapter=6,
            verse_number=35,
            context={"location": "anywhere", "short_descp": "Chapter 6, Verse 35"},
            ai_why=(
                "The Gita acknowledges the mind's restless nature 5,000 years before "
                "neuroscience confirmed it. Default Mode Network (DMN) research shows "
                "the untrained mind wanders ~47% of waking hours (Killingsworth & Gilbert, 2010). "
                "Abhyasa (practice) and vairagya (detachment) are the prescribed antidotes — "
                "mirroring modern mindfulness-based stress reduction (MBSR)."
            ),
            sanskrit_text="असंशयं महाबाहो मनो दुर्निग्रहं चलम्। अभ्यासेन तु कौन्तेय वैराग्येण च गृह्यते॥",
            transliteration=(
                "Asanshayam maha-baho mano durnigraham chalam, "
                "abhyasena tu kaunteya vairagyena cha grihyate"
            ),
            english_translation=(
                "Undoubtedly, O mighty-armed Arjuna, the mind is restless and very difficult "
                "to control. But it can be restrained through practice (abhyasa) "
                "and detachment (vairagya)."
            ),
            commentary=(
                "Krishna validates Arjuna's frustration — the mind IS hard to tame — "
                "then offers a practical framework: repeated practice combined with letting go. "
                "This is the earliest known formulation of what cognitive science now calls "
                "'deliberate practice' paired with 'cognitive defusion' (Hayes, 2004)."
            ),
            audio_url="",
            icon_url="",
        ),
        # 4 — BG 12.13: grateful / happy / peaceful
        GitaVerse(
            title="Bhagavad Gita 12.13 — The Marks of a True Devotee",
            emoji="🌸",
            subtitle="Adveshta sarva-bhutanam",
            duration_mins=5,
            chapter=12,
            verse_number=13,
            context={"location": "anywhere", "short_descp": "Chapter 12, Verse 13"},
            ai_why=(
                "Gratitude practice rewires the brain's reward system. Studies (Emmons & McCullough, 2003) "
                "show gratitude journaling increases well-being by 25%. This verse describes the "
                "ideal devotee as one free from hatred and full of compassion — qualities that "
                "positive psychology identifies as key predictors of sustained happiness."
            ),
            sanskrit_text="अद्वेष्टा सर्वभूतानां मैत्रः करुण एव च। निर्ममो निरहङ्कारः समदुःखसुखः क्षमी॥",
            transliteration=(
                "Adveshta sarva-bhutanam maitrah karuna eva cha, "
                "nirmamo nirahankarah sama-duhkha-sukhah kshami"
            ),
            english_translation=(
                "One who bears no hatred toward any living being, who is friendly and compassionate, "
                "free from possessiveness and ego, equal in joy and sorrow, and forgiving."
            ),
            commentary=(
                "Krishna describes the qualities of a person dear to the divine — not through rituals "
                "but through character. Modern research on prosocial behaviour confirms that "
                "compassion, forgiveness, and ego-reduction are among the strongest predictors "
                "of life satisfaction and neural well-being (Davidson & Begley, 2012)."
            ),
            audio_url="",
            icon_url="",
        ),
        # 5 — BG 3.8: tired / exhausted / drained
        GitaVerse(
            title="Bhagavad Gita 3.8 — The Duty of Righteous Action",
            emoji="☀️",
            subtitle="Niyatam kuru karma tvam",
            duration_mins=5,
            chapter=3,
            verse_number=8,
            context={"location": "anywhere", "short_descp": "Chapter 3, Verse 8"},
            ai_why=(
                "When exhausted, the mind gravitates toward inaction. But behavioural activation "
                "therapy (Jacobson et al., 2001) shows that small purposeful actions — even when "
                "fatigued — break the lethargy cycle by stimulating dopaminergic reward pathways. "
                "Krishna's instruction to perform one's duty mirrors this: act, even minimally, "
                "because inaction deepens the fatigue spiral."
            ),
            sanskrit_text="नियतं कुरु कर्म त्वं कर्म ज्यायो ह्यकर्मणः। शरीरयात्रापि च ते न प्रसिद्ध्येदकर्मणः॥",
            transliteration=(
                "Niyatam kuru karma tvam karma jyayo hyakarmanah, "
                "sharira-yatrapi cha te na prasiddhyed akarmanah"
            ),
            english_translation=(
                "Perform your prescribed duty, for action is better than inaction. "
                "Even the maintenance of your body would not be possible through inaction."
            ),
            commentary=(
                "Krishna makes a practical, almost biological argument: your body cannot sustain "
                "itself without action. Modern exercise physiology agrees — even minimal movement "
                "(a 10-minute walk) releases endorphins and BDNF (brain-derived neurotrophic factor), "
                "reducing fatigue more effectively than rest alone (Puetz et al., 2006)."
            ),
            audio_url="",
            icon_url="",
        ),
    ]


# ── Punya (Acts of Kindness) ─────────────────────────────────────────────────

def _punya_activities() -> list[Punya]:
    return [
        Punya(
            title="Pay for a stranger's chai",
            emoji="🌻",
            subtitle="A small act of kindness",
            duration_mins=5,
            context={"location": "anywhere", "short_descp": "Pay for a stranger's tea or donate a small amount via UPI"},
            activity=(
                "Next time you're at a tea stall or cafe, pay for the person behind you. "
                "If you're working from home, transfer ₹20 to a local street vendor via UPI."
            ),
            ai_why=(
                "Prosocial spending — spending money on others rather than yourself — "
                "activates the nucleus accumbens (reward centre) more strongly than "
                "self-directed spending (Dunn et al., 2008, Science). "
                "Even a small act triggers an oxytocin release cycle, improving your "
                "own mood for up to 2 hours post-action."
            ),
            icon_url="",
        ),
        Punya(
            title="Write a thank-you note",
            emoji="💛",
            subtitle="Express genuine appreciation",
            duration_mins=10,
            context={"location": "anywhere", "short_descp": "Write a heartfelt thank-you message to someone who helped you"},
            activity=(
                "Think of someone who made a difference in your life recently — "
                "a colleague, friend, parent, or even a delivery person. "
                "Write them a genuine 3-4 line message of thanks and send it now."
            ),
            ai_why=(
                "Gratitude expression activates the medial prefrontal cortex and "
                "produces lasting neural changes. A landmark study (Seligman et al., 2005) "
                "found that writing and delivering a gratitude letter produced the single "
                "largest positive psychology intervention effect, with mood benefits "
                "lasting up to one month."
            ),
            icon_url="",
        ),
        Punya(
            title="Feed street animals",
            emoji="🐾",
            subtitle="Nourish a fellow being",
            duration_mins=10,
            context={"location": "anywhere", "short_descp": "Buy biscuits or grain and feed stray dogs, cats, or birds near you"},
            activity=(
                "Pick up a packet of biscuits or a handful of grain. Step outside "
                "and feed the stray dogs, cats, or birds in your area. "
                "Sit quietly for a moment and watch them eat."
            ),
            ai_why=(
                "Human-animal interaction triggers oxytocin release in both the human "
                "and the animal (Handlin et al., 2011). The act of nurturing activates "
                "the caregiving neural circuit (ventral tegmental area → nucleus accumbens), "
                "producing a potent anti-anxiety effect comparable to low-dose SSRIs."
            ),
            icon_url="",
        ),
        Punya(
            title="Help an elderly neighbour",
            emoji="🙏",
            subtitle="Lend a hand to someone nearby",
            duration_mins=15,
            context={"location": "home", "short_descp": "Help an elderly neighbour carry groceries or assist with a small task"},
            activity=(
                "Check on an elderly neighbour today. Offer to carry their groceries, "
                "help with a household task, or simply sit with them for 10 minutes "
                "and listen to a story from their life."
            ),
            ai_why=(
                "Intergenerational social contact reduces loneliness biomarkers in both "
                "parties. The 'tend-and-befriend' response (Taylor et al., 2000) shows "
                "that caregiving behaviour suppresses cortisol and activates the "
                "parasympathetic nervous system, reducing stress at a physiological level."
            ),
            icon_url="",
        ),
        Punya(
            title="Plant a sapling or water plants",
            emoji="🌿",
            subtitle="Nurture greenery around you",
            duration_mins=15,
            context={"location": "anywhere", "short_descp": "Plant a sapling, water your garden, or gift a small plant to someone"},
            activity=(
                "Plant a sapling in your garden, balcony, or a public space. "
                "If planting isn't possible today, water your existing plants mindfully — "
                "notice the soil, the leaves, the quiet act of nurturing life."
            ),
            ai_why=(
                "Horticultural therapy research (Soga et al., 2017) demonstrates that "
                "gardening reduces cortisol levels by 11.4% more than indoor relaxation. "
                "Contact with soil microbiome (Mycobacterium vaccae) stimulates serotonin "
                "production, a natural antidepressant pathway discovered by Lowry et al. (2007)."
            ),
            icon_url="",
        ),
    ]


# ── Breathing Exercises ───────────────────────────────────────────────────────

def _breathing_exercises() -> list[Breathing]:
    return [
        Breathing(
            title="Nadi Shodhana — Alternate Nostril Breathing",
            emoji="🧘",
            subtitle="Balance your hemispheres",
            duration_mins=5,
            context={
                "location": "anywhere",
                "short_descp": "Alternate nostril breathing to balance brain hemispheres and reduce anxiety",
            },
            ai_why=(
                "Alternating nostril breathing balances activity between the left "
                "(parasympathetic) and right (sympathetic) hemispheres of the brain. "
                "EEG studies (Telles et al., 1994) demonstrate increased alpha-wave "
                "activity and subjective calmness within 5 minutes of practice. "
                "The technique also increases blood oxygen saturation by ~2-3%."
            ),
            audio_url="",
            icon_url="",
            duration_seconds=300,
            animation="pulse",
            breath_phases=[
                BreathPhase(name="INHALE", seconds=4, instruction="Breathe in through your left nostril"),
                BreathPhase(name="EXHALE", seconds=4, instruction="Breathe out through your right nostril"),
            ],
            cycles=10,
            steps=[
                "Sit comfortably with your spine straight.",
                "Close your right nostril with your right thumb.",
                "Inhale slowly through your left nostril for 4 counts.",
                "Close your left nostril with your ring finger, release your thumb.",
                "Exhale through your right nostril for 4 counts.",
                "Inhale through your right nostril, then switch. Repeat for 10 cycles.",
            ],
        ),
        Breathing(
            title="Sama Vritti — Box Breathing",
            emoji="🌊",
            subtitle="Equal-ratio calm",
            duration_mins=4,
            context={
                "location": "anywhere",
                "short_descp": "Box breathing (4-4-4-4) used by Navy SEALs for instant calm under pressure",
            },
            ai_why=(
                "Box breathing synchronises the heart rate with the breath cycle, "
                "maximising heart rate variability (HRV). Used by U.S. Navy SEALs "
                "for high-stress performance, peer-reviewed trials (Ma et al., 2017) "
                "show a 15% reduction in self-reported anxiety after just 5 minutes. "
                "The equal-ratio pattern activates the vagus nerve bilaterally."
            ),
            audio_url="",
            icon_url="",
            duration_seconds=240,
            animation="hold-pulse",
            breath_phases=[
                BreathPhase(name="INHALE", seconds=4, instruction="Breathe in slowly through your nose"),
                BreathPhase(name="HOLD", seconds=4, instruction="Hold gently — no strain"),
                BreathPhase(name="EXHALE", seconds=4, instruction="Slow release through your mouth"),
                BreathPhase(name="HOLD", seconds=4, instruction="Pause before the next inhale"),
            ],
            cycles=4,
            steps=[
                "Sit upright in a comfortable position.",
                "Exhale all the air from your lungs.",
                "Inhale through your nose for exactly 4 counts.",
                "Hold your breath for 4 counts.",
                "Exhale slowly for 4 counts.",
                "Hold empty for 4 counts. Repeat 4 cycles.",
            ],
        ),
        Breathing(
            title="4-7-8 Relaxation Breath",
            emoji="🌸",
            subtitle="Dr Weil's sleep technique",
            duration_mins=3,
            context={
                "location": "anywhere",
                "short_descp": "4-7-8 breathing pattern for deep relaxation and sleep preparation",
            },
            ai_why=(
                "Popularised by Dr Andrew Weil and rooted in Pranayama, the extended "
                "exhale (twice the inhale length) stimulates the parasympathetic nervous "
                "system. The prolonged breath-hold increases alveolar CO₂, which dilates "
                "blood vessels and promotes muscular relaxation. Clinical trials show "
                "improved sleep onset latency by up to 20 minutes (Jerath et al., 2015)."
            ),
            audio_url="",
            icon_url="",
            duration_seconds=180,
            animation="asymmetric",
            breath_phases=[
                BreathPhase(name="INHALE", seconds=4, instruction="Breathe in through your nose"),
                BreathPhase(name="HOLD", seconds=7, instruction="Hold gently — no strain"),
                BreathPhase(name="EXHALE", seconds=8, instruction="Slow release through mouth — whooshing sound"),
            ],
            cycles=4,
            steps=[
                "Place the tip of your tongue against the ridge behind your upper front teeth.",
                "Exhale completely through your mouth with a whooshing sound.",
                "Close your mouth. Inhale through your nose for exactly 4 counts.",
                "Hold your breath for exactly 7 counts.",
                "Exhale completely through your mouth, making a whoosh sound, for exactly 8 counts. Repeat 4 cycles.",
            ],
        ),
        Breathing(
            title="Bhramari — Humming Bee Breath",
            emoji="🐝",
            subtitle="Vibration-based calm",
            duration_mins=5,
            context={
                "location": "anywhere",
                "short_descp": "Humming exhalation that calms the mind through cranial vibration",
            },
            ai_why=(
                "The humming exhalation in Bhramari creates vibrations at ~130 Hz in "
                "the cranial cavity, stimulating the vagus nerve and increasing nitric "
                "oxide production in the paranasal sinuses by up to 15-fold (Weitzberg & "
                "Lundberg, 2002). fMRI studies show reduced amygdala activity within "
                "3 minutes of practice, mirroring effects of anti-anxiety medication."
            ),
            audio_url="",
            icon_url="",
            duration_seconds=300,
            animation="vibrate",
            breath_phases=[
                BreathPhase(name="INHALE", seconds=4, instruction="Breathe in deeply through your nose"),
                BreathPhase(name="EXHALE", seconds=6, instruction="Exhale with a steady humming sound"),
            ],
            cycles=7,
            steps=[
                "Sit comfortably and close your eyes.",
                "Place your index fingers gently on the tragus cartilage of each ear.",
                "Inhale deeply through your nose for 4 counts.",
                "While exhaling, make a steady humming sound like a bee for 6 counts.",
                "Feel the vibrations in your forehead and jaw.",
                "Repeat for 7 cycles, keeping the humming pitch steady.",
            ],
        ),
        Breathing(
            title="Kapalabhati — Skull Shining Breath",
            emoji="✨",
            subtitle="Energising cleanse",
            duration_mins=3,
            context={
                "location": "anywhere",
                "short_descp": "Rapid rhythmic exhalations to boost energy and clear mental fog",
            },
            ai_why=(
                "Kapalabhati's rapid diaphragmatic contractions increase blood oxygen "
                "saturation and stimulate the sympathetic nervous system briefly, "
                "followed by a parasympathetic rebound. Studies (Stancak et al., 1991) "
                "show increased EEG beta-wave activity (alertness) during practice and "
                "enhanced alpha-wave activity (calm) immediately after — a unique "
                "'alert-yet-calm' state ideal for clearing mental fog."
            ),
            audio_url="",
            icon_url="",
            duration_seconds=180,
            animation="rapid",
            breath_phases=[
                BreathPhase(name="EXHALE", seconds=1, instruction="Sharp forceful exhale through your nose"),
                BreathPhase(name="INHALE", seconds=1, instruction="Allow passive inhale — belly relaxes naturally"),
            ],
            cycles=30,
            steps=[
                "Sit tall with hands on your knees.",
                "Take a deep breath in to prepare.",
                "Forcefully exhale through your nose by contracting your lower belly sharply.",
                "Allow the inhale to happen passively as your belly relaxes.",
                "Start slowly (1 per second), then build speed to 2 per second.",
                "Complete 30 rapid cycles, then rest with 3 deep breaths. Repeat the set.",
            ],
        ),
    ]


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
            Breathing,
            Punya,
            DailyPanchang,
            RecipeRequest,
        ],
    )

    # ── Gita Verses ───────────────────────────────────────────────────────────
    print("Seeding Gita verses (5)...")
    for verse in _gita_verses():
        existing = await GitaVerse.find_one(
            {"chapter": verse.chapter, "verse_number": verse.verse_number}
        )
        if existing is None:
            await verse.insert()
            print(f"  + Inserted BG {verse.chapter}.{verse.verse_number}: {verse.title}")
        else:
            print(f"  - Skipped  BG {verse.chapter}.{verse.verse_number} (already exists)")

    # ── Punya Activities ──────────────────────────────────────────────────────
    print("\nSeeding Punya activities (5)...")
    for punya in _punya_activities():
        existing = await Punya.find_one({"title": punya.title})
        if existing is None:
            await punya.insert()
            print(f"  + Inserted PUNYA: {punya.title}")
        else:
            print(f"  - Skipped  PUNYA: {punya.title} (already exists)")

    # ── Breathing Exercises ───────────────────────────────────────────────────
    print("\nSeeding Breathing exercises (5)...")
    for breathing in _breathing_exercises():
        existing = await Breathing.find_one({"title": breathing.title})
        if existing is None:
            await breathing.insert()
            print(f"  + Inserted BREATHING: {breathing.title}")
        else:
            print(f"  - Skipped  BREATHING: {breathing.title} (already exists)")

    print("\n✅ Recipe seed complete — 15 ingredients ready.")
    print("   Gita verses will appear in AI context as: 'Chapter X, Verse Y'")
    print("   Mock service always picks selected_number=1 for all categories.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
