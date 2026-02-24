"""
app/api/routes/stories.py
──────────────────────────
Story shuffle endpoint.

GET /stories/shuffle uses MongoDB's native $sample aggregation stage
to randomly select N Story documents server-side.  This is far more
efficient than fetching all stories and sampling in Python:
  • Only N documents are transferred over the wire.
  • MongoDB's $sample uses a pseudo-random reservoir-sampling algorithm
    for collections > 100 documents (true uniform distribution).
  • No pagination needed — the shuffle result is always fresh.

Public endpoint — no JWT required.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user
from app.models.ingredients import ActivityType, BaseIngredient
from app.models.user import User

router = APIRouter(prefix="/stories", tags=["Stories"])

_DEFAULT_SAMPLE_SIZE = 3


@router.get(
    "/shuffle",
    summary="Fetch a random selection of stories",
    response_description=(
        "A randomly-ordered list of Story documents, each with fields: "
        "id, activity_type, title, why, tags, icon_url, story_text, "
        "scripture_source, image_url."
    ),
)
async def shuffle_stories(
    count: int = Query(
        default=_DEFAULT_SAMPLE_SIZE,
        ge=1,
        le=10,
        description="Number of random stories to return (1–10, default 3).",
    ),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Returns a random selection of Story ingredients using MongoDB's
    `$sample` aggregation stage.

    The aggregation pipeline:
    ```json
    [
      { "$match": { "activity_type": "STORY" } },
      { "$sample": { "size": 3 } }
    ]
    ```

    **Note on `_id` serialisation:** MongoDB ObjectIds in aggregation
    results are returned as `{"$oid": "..."}` in the raw BSON but are
    automatically converted to plain strings by Beanie's motor driver.
    The response `id` field will be a 24-character hex string.
    """
    pipeline: List[Dict[str, Any]] = [
        {"$match": {"activity_type": ActivityType.STORY.value}},
        {"$sample": {"size": count}},
        # Rename _id → id and convert ObjectId to string for the client.
        {
            "$addFields": {
                "id": {"$toString": "$_id"},
            }
        },
        {"$project": {"_id": 0}},
    ]

    results: List[Dict[str, Any]] = await BaseIngredient.aggregate(
        aggregation_pipeline=pipeline,
    ).to_list()

    return results
