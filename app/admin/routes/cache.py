"""
app/admin/routes/cache.py
─────────────────────────
Admin endpoint for invalidating the in-memory ingredient cache.

The ingredient cache stores lightweight summaries of GITA, PUNYA, and
BREATHING activities so the AI has fast access to context data.  After
an admin adds, updates, or deletes ingredients via the admin panel, this
endpoint can be called to force the cache to refresh on the next read.

Usage:
  POST /admin/cache/invalidate              → clear entire cache
  POST /admin/cache/invalidate?type=punya   → clear only PUNYA entries
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.admin.dependencies import get_current_admin
from app.models.user import User
from app.services.ingredient_cache import get_ingredient_cache

router = APIRouter(prefix="/admin/cache", tags=["admin-cache"])


@router.post("/invalidate")
async def invalidate_cache(
    type: Optional[str] = Query(
        None,
        description=(
            "Activity type to invalidate: gita, punya, or breathing. "
            "Omit to clear the entire cache."
        ),
    ),
    _admin: User = Depends(get_current_admin),
):
    """
    Invalidate the in-memory ingredient cache so the next AI recipe
    request fetches fresh data from the database.

    - **No query param** → clears all cached activity types.
    - **?type=punya** → clears only the PUNYA cache (gita/breathing stay warm).
    """
    cache = get_ingredient_cache()
    invalidated_keys = cache.invalidate(type)

    return {
        "success": True,
        "invalidated": invalidated_keys,
        "message": (
            f"Cleared cache for: {', '.join(invalidated_keys)}"
            if invalidated_keys
            else "Nothing to invalidate (cache was already empty for the requested type)."
        ),
    }
