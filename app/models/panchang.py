"""
app/models/panchang.py
──────────────────────
Beanie Document model for the `panchang` MongoDB collection.

What is a Panchang?
  The Panchang (Sanskrit: पञ्चाङ्ग, "five limbs") is the traditional Hindu
  lunisolar almanac.  Its five elements are:
    1. Tithi     – Lunar day (1–30), each ~23 h 37 min long.
    2. Vara      – Day of the week (named after planets).
    3. Nakshatra – Lunar mansion (~13.3° arc of the ecliptic).
    4. Yoga      – A combined Sun+Moon longitude measure (27 types).
    5. Karana    – Half of a Tithi (11 types).

Data source:
  Scraped via scripts/panchang_scraper/.
  The full scraper output (~60+ fields across 12 sections) is stored
  in `raw_data` as a flexible dict.  Core fields are promoted to
  top-level typed attributes for fast API queries.

Indexing:
  A compound unique index on (date, city) prevents duplicate entries and
  enables O(1) lookups for the GET /cosmic endpoint.
"""

from datetime import date
from typing import Any, Dict, List

from beanie import Document, Indexed
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class DailyPanchang(Document):
    """
    Daily Panchang snapshot for a specific city and date.

    Populated by the scrape-panchang GitHub Actions workflow which runs
    the panchang scraper and writes to Cosmos DB.
    """

    # ── Primary lookup key ────────────────────────────────────────────────────
    date: Indexed(date)
    city: Indexed(str)

    # ── Core panchang fields (promoted for fast queries) ──────────────────────
    tithi: str = Field(default="", description="Lunar day name. E.g. 'Tritiya'.")
    nakshatra: str = Field(default="", description="Lunar mansion (one of 27).")
    yoga: str = Field(default="", description="One of 27 Panchang yogas.")
    karana: str = Field(default="", description="Half-tithi element (one of 11).")
    paksha: str = Field(default="", description="'Shukla Paksha' or 'Krishna Paksha'.")
    sunrise: str = Field(default="", description="Local sunrise time.")
    sunset: str = Field(default="", description="Local sunset time.")

    # ── Full scraper data ─────────────────────────────────────────────────────
    raw_data: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Complete scraper output for this city+date. Contains all 12 sections: "
            "sunrise_and_moonrise, panchang, rashi_and_nakshatra, ritu_and_ayana, "
            "auspicious_timings, inauspicious_timings, anandadi_and_tamil_yoga, "
            "nivas_and_shool, other_calendars_and_epoch, day_festivals_and_events, "
            "lunar_month_samvat, mantri_mandala, header."
        ),
    )

    # ── AI-generated inferences (populated later) ─────────────────────────────
    inferences: List[str] = Field(
        default_factory=list,
        description=(
            "AI-generated scientific/biological observations correlated with "
            "today's cosmic state. Will be populated in Phase 2."
        ),
    )

    class Settings:
        name = "panchang"
        indexes = [
            IndexModel(
                [("date", ASCENDING), ("city", ASCENDING)],
                unique=True,
            ),
        ]
