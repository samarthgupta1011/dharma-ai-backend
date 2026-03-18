"""
app/services/panchang_ai.py
────────────────────────────
Lazy AI inference generator for panchang data.

When a user opens the Panchang tab for a city+date, the API checks
if inferences already exist. If not, this service generates them via
OpenAI and caches them on the DailyPanchang document.

Subsequent users for the same city+date get cached results instantly.
"""

import json
import logging
from typing import Any, Dict, List

from openai import AsyncOpenAI

from app.config.settings import get_settings
from app.prompts.panchang_prompts import PANCHANG_INFERENCE_PROMPT, PANCHANG_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_settings = get_settings()


async def generate_panchang_inferences(raw_data: Dict[str, Any]) -> List[str]:
    """
    Generate scientific/biological inferences from panchang data using OpenAI.

    Returns a list of 3-5 inference strings. If OpenAI is disabled or fails,
    returns an empty list (graceful degradation).
    """
    if not _settings.ENABLE_OPENAI:
        return _mock_inferences(raw_data)

    try:
        client = AsyncOpenAI(api_key=_settings.OPENAI_API_KEY)

        # Build a concise summary of the panchang data for the prompt
        panchang_summary = _build_summary(raw_data)

        user_prompt = PANCHANG_INFERENCE_PROMPT.format(
            panchang_data=panchang_summary,
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PANCHANG_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=600,
        )

        response_text = response.choices[0].message.content
        if not response_text:
            return []

        # Parse JSON array of strings
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        inferences = json.loads(cleaned)
        if isinstance(inferences, list):
            return [str(i) for i in inferences[:5]]
        return []

    except Exception:
        logger.exception("Failed to generate panchang inferences")
        return []


def _build_summary(raw_data: Dict[str, Any]) -> str:
    """Build a concise text summary of panchang data for the AI prompt."""
    parts = []

    panchang = raw_data.get("panchang", {})
    if panchang:
        parts.append(f"Tithi: {panchang.get('tithi', 'N/A')}")
        parts.append(f"Nakshatra: {panchang.get('nakshatra', 'N/A')}")
        parts.append(f"Yoga: {panchang.get('yoga', 'N/A')}")
        parts.append(f"Karana: {panchang.get('karana', 'N/A')}")
        parts.append(f"Paksha: {panchang.get('paksha', 'N/A')}")

    sunrise = raw_data.get("sunrise_and_moonrise", {})
    if sunrise:
        parts.append(f"Sunrise: {sunrise.get('sunrise', 'N/A')}")
        parts.append(f"Sunset: {sunrise.get('sunset', 'N/A')}")
        parts.append(f"Moonrise: {sunrise.get('moonrise', 'N/A')}")

    rashi = raw_data.get("rashi_and_nakshatra", {})
    if rashi:
        parts.append(f"Moon Sign: {rashi.get('moonsign', 'N/A')}")
        parts.append(f"Sun Sign: {rashi.get('sunsign', 'N/A')}")

    auspicious = raw_data.get("auspicious_timings", {})
    if auspicious:
        items = [f"{k}: {v}" for k, v in list(auspicious.items())[:4]]
        parts.append("Auspicious: " + ", ".join(items))

    festivals = raw_data.get("day_festivals_and_events", {})
    if festivals and festivals.get("festivals"):
        parts.append(f"Festivals: {', '.join(festivals['festivals'][:3])}")

    return "\n".join(parts)


def _mock_inferences(raw_data: Dict[str, Any]) -> List[str]:
    """Return placeholder inferences when OpenAI is disabled."""
    panchang = raw_data.get("panchang", {})
    tithi = panchang.get("tithi", "today's tithi")
    paksha = panchang.get("paksha", "")

    inferences = [
        f"During {tithi}, the lunar gravitational influence on Earth's tidal forces shifts subtly — research suggests this may affect sleep patterns and fluid retention.",
    ]

    if "shukla" in paksha.lower():
        inferences.append(
            "Shukla Paksha (waxing moon) is associated with increasing light and energy. Studies on circadian biology suggest brighter nighttime conditions can elevate alertness."
        )
    elif "krishna" in paksha.lower():
        inferences.append(
            "Krishna Paksha (waning moon) correlates with decreasing ambient nighttime light. Sleep research indicates darker nights may support deeper, more restorative sleep."
        )

    inferences.append(
        "The practice of aligning daily activities with cosmic cycles has parallels in chronobiology — the study of how biological rhythms interact with environmental cycles."
    )

    return inferences
