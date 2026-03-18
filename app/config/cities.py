"""
app/config/cities.py
────────────────────
Single source of truth for supported Panchang cities.

Used by:
  1. GitHub Actions scraper — knows which cities to scrape
  2. GET /metadata/configs   — serves city list to mobile app
  3. GET /cosmic             — validates city parameter
  4. scripts/panchang_scraper — imports this for city→GeoName mapping

GeoName IDs are standard identifiers from geonames.org, used to
calculate location-specific astronomical data (sunrise, moonrise,
directional timings, etc.).
"""

# City name → GeoName ID mapping
# To add a new city:
#   1. Find its GeoName ID at https://www.geonames.org/
#   2. Add it here
#   3. Trigger the scrape-panchang GitHub Action — it will backfill from 2026-01-01
SUPPORTED_CITIES: dict[str, int] = {
    # ── India (10 cities) ─────────────────────────────────────────────────────
    # Major metros + culturally significant Hindu cities
    "Delhi": 1273294,
    "Mumbai": 1275339,
    "Bangalore": 1277333,
    "Hyderabad": 1269843,
    "Chennai": 1264527,
    "Pune": 1259229,
    "Jaipur": 1269515,
    "Varanasi": 1253405,       # Oldest living city, Shiva's city, spiritual capital
    "Ahmedabad": 1279233,
    "Lucknow": 1264733,

    # ── Diaspora (8 cities) ───────────────────────────────────────────────────
    # Largest Hindu/Indian diaspora populations
    "London": 2643743,         # Largest Indian diaspora in Europe
    "Toronto": 6167865,        # ~700K+ South Asian community
    "Singapore": 1880252,      # ~400K+ Indians, strong Hindu community
    "New York": 5128581,       # Largest US metro Indian population
    "San Francisco": 5391959,  # Bay Area — massive tech Indian community
    "Chicago": 4887398,        # 3rd largest US Indian population
    "Houston": 4699066,        # Large Indian community, major temples
    "Dallas": 4684904,         # Fast-growing Indian population in Texas
}

# The earliest date we want panchang data for
PANCHANG_DATA_START = "2026-01-01"
