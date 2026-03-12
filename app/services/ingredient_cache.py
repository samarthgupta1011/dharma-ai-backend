"""
app/services/ingredient_cache.py
─────────────────────────────────
Lightweight in-memory cache for ingredient context data.

Only stores the fields needed to build AI context strings
(id, context).  Full documents are fetched by ID
from the database only after the AI selects a specific item.

Features:
  • TTL-based auto-expiry (default 5 minutes).
  • Manual invalidation via invalidate() — called by the admin
    cache-invalidation endpoint or any other write path.
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from beanie import PydanticObjectId

from app.models.ingredients import Breathing, GitaVerse, Punya

logger = logging.getLogger(__name__)

# Default cache time-to-live in seconds.
DEFAULT_TTL_SECONDS = 300  # 5 minutes


@dataclass(frozen=False)
class CachedIngredient:
    """Minimal projection of an ingredient stored in the cache."""

    id: PydanticObjectId
    context: Dict[str, str]


# Mapping from cache keys to the Beanie model used for DB queries.
_MODEL_MAP = {
    "punya": Punya,
    "breathing": Breathing,
    "gita": GitaVerse,
}


class IngredientCache:
    """
    In-memory TTL cache for GITA, PUNYA, and BREATHING ingredient summaries.

    Thread-safety note: asyncio is single-threaded so no locking is
    required for dict mutations — only one coroutine runs at a time.
    """

    def __init__(self, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl
        # key → (timestamp, items)
        self._store: Dict[str, tuple[float, List[CachedIngredient]]] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    async def get(self, activity_type: str) -> List[CachedIngredient]:
        """
        Return cached ingredient summaries for *activity_type*.

        On a cache miss (or expiry) the data is fetched from MongoDB,
        projected into CachedIngredient instances, and stored.
        """
        key = activity_type.lower()
        now = time.monotonic()

        entry = self._store.get(key)
        if entry is not None:
            ts, items = entry
            if now - ts < self._ttl:
                logger.debug("ingredient_cache HIT  key=%s  items=%d", key, len(items))
                return items
            # Expired — fall through to refresh.
            logger.debug("ingredient_cache EXPIRED  key=%s", key)

        return await self._refresh(key)

    def invalidate(self, activity_type: Optional[str] = None) -> List[str]:
        """
        Invalidate cached entries.

        Args:
            activity_type: e.g. "PUNYA" or "breathing".
                           If None, the entire cache is cleared.

        Returns:
            List of cache keys that were invalidated.
        """
        if activity_type is not None:
            key = activity_type.lower()
            if key in self._store:
                del self._store[key]
                logger.info("ingredient_cache INVALIDATED  key=%s", key)
                return [key]
            return []

        keys = list(self._store.keys())
        self._store.clear()
        logger.info("ingredient_cache INVALIDATED  all keys=%s", keys)
        return keys

    # ── Internals ─────────────────────────────────────────────────────────────

    async def _refresh(self, key: str) -> List[CachedIngredient]:
        """Fetch ingredients from DB, project into CachedIngredient, store."""
        model = _MODEL_MAP.get(key)
        if model is None:
            logger.warning("ingredient_cache: unknown key '%s'", key)
            return []

        docs = await model.find_all().to_list()
        items = [
            CachedIngredient(
                id=doc.id,
                context=doc.context or {},
            )
            for doc in docs
        ]
        self._store[key] = (time.monotonic(), items)
        logger.info(
            "ingredient_cache REFRESHED  key=%s  items=%d", key, len(items)
        )
        return items


# ── Module-level singleton ────────────────────────────────────────────────────

_ingredient_cache: Optional[IngredientCache] = None


def get_ingredient_cache() -> IngredientCache:
    """Return (and lazily create) the singleton IngredientCache."""
    global _ingredient_cache
    if _ingredient_cache is None:
        _ingredient_cache = IngredientCache()
    return _ingredient_cache
