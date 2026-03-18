"""
app/api/routes/cosmic.py
─────────────────────────
Panchang (Hindu almanac) data endpoint.

GET /cosmic returns the DailyPanchang for a given city and date,
including AI-generated scientific inferences.

Data flow:
  1. Panchang raw data is pre-populated by the scrape-panchang
     GitHub Actions workflow (scripts/panchang_scraper/).
  2. GET /cosmic looks up the document by (city, date).
  3. If inferences are empty (first access for this city+date),
     generates them via OpenAI and caches on the document.
  4. Subsequent requests return cached data instantly.
"""

import datetime as dt
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user
from app.config.cities import SUPPORTED_CITIES
from app.models.panchang import DailyPanchang
from app.models.user import User
from app.services.panchang_ai import generate_panchang_inferences

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cosmic", tags=["Cosmic / Panchang"])


@router.get(
    "/",
    summary="Fetch Panchang for a city and date",
    response_description="Panchang data with scientific inferences.",
)
async def get_panchang(
    city: str = Query(
        ...,
        description="City name from supported_cities in /metadata/configs.",
        examples=["Mumbai"],
    ),
    query_date: Optional[dt.date] = Query(
        default=None,
        alias="date",
        description=(
            "ISO 8601 date (YYYY-MM-DD). "
            "Omit to get today's panchang."
        ),
        examples=["2026-04-15"],
    ),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Returns the Panchang for the requested city and date, along with
    AI-generated scientific inferences.

    Inferences are generated on first access and cached — subsequent
    requests for the same city+date return instantly.
    """
    # Validate city
    if city not in SUPPORTED_CITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported city: '{city}'. Use /metadata/configs for the list.",
        )

    target_date = query_date or dt.date.today()

    panchang = await DailyPanchang.find_one(
        DailyPanchang.city == city,
        DailyPanchang.date == target_date,
    )

    if panchang is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Panchang data for city='{city}' on {target_date}.",
        )

    # Lazy inference generation — first user triggers AI, rest get cache
    if not panchang.inferences and panchang.raw_data:
        inferences = await generate_panchang_inferences(panchang.raw_data)
        if inferences:
            panchang.inferences = inferences
            await panchang.save()

    return panchang.model_dump(mode="json")
