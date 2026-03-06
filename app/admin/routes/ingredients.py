"""
app/admin/routes/ingredients.py
───────────────────────────────
Admin endpoints for creating and managing ingredients.

Key design decisions:
  • POST /admin/ingredients/form-schema: Returns dropdown options and field specs
  • POST /admin/ingredients: Create new ingredient (flexible JSON, no validation)
  • GET /admin/ingredients: List all ingredients (paginated)
  • GET /admin/ingredients/{id}: Get single ingredient
  • PUT /admin/ingredients/{id}: Update ingredient
  • DELETE /admin/ingredients/{id}: Delete ingredient
  • POST /admin/ingredients/{id}/upload: Upload media file and return signed URL

Why no Pydantic validation?
  The schema is still evolving and admin should have flexibility to add
  new fields without waiting for code changes. Beanie will handle basic
  type coercion when saving to MongoDB.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from beanie import PydanticObjectId
from pydantic import BaseModel

from app.admin.dependencies import get_current_admin
from app.admin.services.media_service import (
    MediaUploadService,
    get_media_upload_service,
)
from app.models.ingredients import (
    ActivityType,
    BaseIngredient,
    Breathing,
    Chanting,
    GitaVerse,
    Punya,
    Story,
    Yoga,
)
from app.models.user import User
from app.services.storage_service import get_storage_service


router = APIRouter(prefix="/admin/ingredients", tags=["admin"])

# ── Type Mapping ─────────────────────────────────────────────────────────

TYPE_TO_MODEL: Dict[str, Any] = {
    ActivityType.GITA: GitaVerse,
    ActivityType.YOGA: Yoga,
    ActivityType.BREATHING: Breathing,
    ActivityType.MANTRA: Chanting,
    ActivityType.PUNYA: Punya,
    ActivityType.STORY: Story,
}

# ── Form Field Schema (for frontend dropdown + form builder) ──────────────

class FieldSpec(BaseModel):
    """Specification for a single form field."""
    name: str
    type: str  # e.g. "string", "text", "integer", "float"
    label: str
    required: bool
    placeholder: Optional[str] = None
    description: Optional[str] = None


class ActivityTypeOptionspecs(BaseModel):
    """Form schema for a single activity type."""
    type: str  # ActivityType enum value
    label: str  # Human-readable display name
    required_fields: list[FieldSpec]
    optional_fields: list[FieldSpec]
    media_fields: list[str]  # Fields that can accept file uploads (audio_url, etc)


# Centralized schema definitions (frontend can use this to render dynamic forms)
FORM_SCHEMAS: Dict[str, ActivityTypeOptionspecs] = {
    ActivityType.GITA: ActivityTypeOptionspecs(
        type=ActivityType.GITA,
        label="Gita Verse",
        required_fields=[
            FieldSpec(
                name="title",
                type="string",
                label="Verse Title",
                required=True,
                placeholder="Chapter 2, Verse 47",
                description="Short, memorable title for the verse",
            ),
            FieldSpec(
                name="why",
                type="text",
                label="Scientific/Historical Context",
                required=True,
                description="Why this verse matters today (psychology, neuroscience perspective)",
            ),
            FieldSpec(
                name="sanskrit_text",
                type="text",
                label="Sanskrit Text (Devanagari)",
                required=True,
            ),
            FieldSpec(
                name="transliteration",
                type="text",
                label="Roman Transliteration",
                required=True,
            ),
            FieldSpec(
                name="english_translation",
                type="text",
                label="English Translation",
                required=True,
            ),
            FieldSpec(
                name="commentary",
                type="text",
                label="Commentary",
                required=True,
                description="Contextual commentary linking verse to modern life",
            ),
        ],
        optional_fields=[
            FieldSpec(
                name="audio_url",
                type="file",
                label="Audio (Verse Recitation)",
                required=False,
                description="MP3 file with verse recitation",
            ),
            FieldSpec(
                name="icon_url",
                type="file",
                label="Icon",
                required=False,
            ),
            FieldSpec(
                name="tags",
                type="json",
                label="Tags (JSON)",
                required=False,
                placeholder='{"anxiety": 0.9, "stress": 0.8}',
                description="Semantic keyword → relevance score mapping",
            ),
        ],
        media_fields=["audio_url", "icon_url"],
    ),
    ActivityType.YOGA: ActivityTypeOptionspecs(
        type=ActivityType.YOGA,
        label="Yoga Pose",
        required_fields=[
            FieldSpec(
                name="title",
                type="string",
                label="Pose Name",
                required=True,
                placeholder="Downward Dog",
            ),
            FieldSpec(
                name="why",
                type="text",
                label="Scientific Basis",
                required=True,
                description="Why this pose is beneficial",
            ),
        ],
        optional_fields=[
            FieldSpec(
                name="gif_url",
                type="file",
                label="Animated GIF",
                required=False,
                description="Asana demonstration as animated GIF",
            ),
            FieldSpec(
                name="steps",
                type="json",
                label="Steps (JSON Array)",
                required=False,
                placeholder='["Step 1", "Step 2"]',
            ),
            FieldSpec(
                name="anatomical_focus",
                type="text",
                label="Anatomical Focus",
                required=False,
            ),
            FieldSpec(
                name="icon_url",
                type="file",
                label="Icon",
                required=False,
            ),
            FieldSpec(
                name="tags",
                type="json",
                label="Tags (JSON)",
                required=False,
            ),
        ],
        media_fields=["gif_url", "icon_url"],
    ),
    ActivityType.BREATHING: ActivityTypeOptionspecs(
        type=ActivityType.BREATHING,
        label="Breathing Technique",
        required_fields=[
            FieldSpec(
                name="title",
                type="string",
                label="Technique Name",
                required=True,
                placeholder="4-7-8 Breathing",
            ),
            FieldSpec(
                name="why",
                type="text",
                label="Scientific Basis",
                required=True,
            ),
        ],
        optional_fields=[
            FieldSpec(
                name="audio_url",
                type="file",
                label="Guided Audio",
                required=False,
            ),
            FieldSpec(
                name="duration_seconds",
                type="integer",
                label="Duration (seconds)",
                required=False,
            ),
            FieldSpec(
                name="pattern",
                type="string",
                label="Breath Pattern",
                required=False,
                placeholder="4-7-8",
            ),
            FieldSpec(
                name="icon_url",
                type="file",
                label="Icon",
                required=False,
            ),
            FieldSpec(
                name="tags",
                type="json",
                label="Tags (JSON)",
                required=False,
            ),
        ],
        media_fields=["audio_url", "icon_url"],
    ),
    ActivityType.MANTRA: ActivityTypeOptionspecs(
        type=ActivityType.MANTRA,
        label="Mantra / Chanting",
        required_fields=[
            FieldSpec(
                name="title",
                type="string",
                label="Mantra Name",
                required=True,
            ),
            FieldSpec(
                name="why",
                type="text",
                label="Scientific Basis",
                required=True,
            ),
        ],
        optional_fields=[
            FieldSpec(
                name="audio_url",
                type="file",
                label="Chanting Audio",
                required=False,
            ),
            FieldSpec(
                name="mantra_text",
                type="text",
                label="Mantra Script & Transliteration",
                required=False,
            ),
            FieldSpec(
                name="frequency_hz",
                type="float",
                label="Primary Frequency (Hz)",
                required=False,
            ),
            FieldSpec(
                name="icon_url",
                type="file",
                label="Icon",
                required=False,
            ),
            FieldSpec(
                name="tags",
                type="json",
                label="Tags (JSON)",
                required=False,
            ),
        ],
        media_fields=["audio_url", "icon_url"],
    ),
    ActivityType.PUNYA: ActivityTypeOptionspecs(
        type=ActivityType.PUNYA,
        label="Punya (Good Deed)",
        required_fields=[
            FieldSpec(
                name="title",
                type="string",
                label="Deed Title",
                required=True,
            ),
            FieldSpec(
                name="why",
                type="text",
                label="Why It Matters",
                required=True,
            ),
            FieldSpec(
                name="activity",
                type="text",
                label="Activity (what to do)",
                required=True,
                description="Concrete action the user should take",
            ),
        ],
        optional_fields=[
            FieldSpec(
                name="emoji",
                type="string",
                label="Emoji",
                required=False,
                placeholder="💛",
            ),
            FieldSpec(
                name="subtitle",
                type="string",
                label="Subtitle",
                required=False,
            ),
            FieldSpec(
                name="duration_mins",
                type="integer",
                label="Duration (minutes)",
                required=False,
            ),
            FieldSpec(
                name="location",
                type="string",
                label="Location (work / home / anywhere)",
                required=False,
                placeholder="anywhere",
            ),
            FieldSpec(
                name="short_descp",
                type="text",
                label="Short Description (AI context)",
                required=False,
                description="Brief context passed to AI when listing activities (~15 words)",
            ),
            FieldSpec(
                name="icon_url",
                type="file",
                label="Icon",
                required=False,
            ),
            FieldSpec(
                name="tags",
                type="json",
                label="Tags (JSON)",
                required=False,
            ),
        ],
        media_fields=["icon_url"],
    ),
    ActivityType.STORY: ActivityTypeOptionspecs(
        type=ActivityType.STORY,
        label="Story",
        required_fields=[
            FieldSpec(
                name="title",
                type="string",
                label="Story Title",
                required=True,
            ),
            FieldSpec(
                name="why",
                type="text",
                label="Modern Relevance",
                required=True,
            ),
        ],
        optional_fields=[
            FieldSpec(
                name="story_text",
                type="text",
                label="Story (Markdown)",
                required=False,
            ),
            FieldSpec(
                name="scripture_source",
                type="string",
                label="Scripture Source",
                required=False,
            ),
            FieldSpec(
                name="image_url",
                type="file",
                label="Illustration",
                required=False,
            ),
            FieldSpec(
                name="icon_url",
                type="file",
                label="Icon",
                required=False,
            ),
            FieldSpec(
                name="tags",
                type="json",
                label="Tags (JSON)",
                required=False,
            ),
        ],
        media_fields=["image_url", "icon_url"],
    ),
}


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/form-schema")
async def get_form_schema(current_admin: User = Depends(get_current_admin)):
    """
    Return the form schema for all ingredient types.

    Frontend uses this to render dynamic forms with type-specific fields
    and media upload areas.

    Response:
      {
        "types": [
          {
            "type": "GITA",
            "label": "Gita Verse",
            "required_fields": [...],
            "optional_fields": [...],
            "media_fields": ["audio_url", "icon_url"]
          },
          ...
        ]
      }
    """
    return {
        "types": list(FORM_SCHEMAS.values()),
    }


@router.post("")
async def create_ingredient(
    data: Dict[str, Any],  # Flexible JSON, no Pydantic validation
    current_admin: User = Depends(get_current_admin),
):
    """
    Create a new ingredient with admin-provided data.

    No schema validation — this allows the admin to add any fields
    and iterate on the schema without code changes.

    Auto-populated fields:
      • created_at: current UTC timestamp
      • _class_id: automatically injected by Beanie based on activity_type

    Args:
        data: JSON object with activity_type and related fields
        Example:
          {
            "activity_type": "GITA",
            "title": "Chapter 2, Verse 47",
            "why": "...",
            "sanskrit_text": "...",
            ...
          }

    Returns:
        Created ingredient document (with MongoDB ID)
    """
    activity_type = data.get("activity_type")
    if activity_type not in TYPE_TO_MODEL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid activity_type. Must be one of: {list(ActivityType)}",
        )

    # Add auto-populated fields
    data["created_at"] = datetime.now(timezone.utc)

    # If tags not provided, default to empty dict
    if "tags" not in data:
        data["tags"] = {}

    # Get the correct Beanie model class and instantiate it
    model_class = TYPE_TO_MODEL[activity_type]
    ingredient = model_class(**data)

    # Beanie saves to MongoDB and populates the ID
    await ingredient.insert()

    return {
        "id": str(ingredient.id),
        "activity_type": ingredient.activity_type,
        "title": ingredient.title,
        "created_at": ingredient.created_at,
    }


@router.get("")
async def list_ingredients(
    activity_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin),
):
    """
    List all ingredients (optionally filtered by type).

    Query params:
      • activity_type: Filter by type (GITA, YOGA, etc.) — optional
      • skip: Number of documents to skip
      • limit: Number of documents to return
    """
    # Build query filter
    query_filter = {}
    if activity_type:
        # Validate the activity_type value
        if activity_type not in [t.value for t in ActivityType]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid activity_type. Must be one of: {[t.value for t in ActivityType]}",
            )
        query_filter = {"activity_type": activity_type}

    # Use raw MongoDB query through Beanie with with_children=True for polymorphic models
    if query_filter:
        total = await BaseIngredient.find(query_filter, with_children=True).count()
        items = (
            await BaseIngredient.find(query_filter, with_children=True)
            .skip(skip)
            .limit(limit)
            .to_list()
        )
    else:
        total = await BaseIngredient.find(with_children=True).count()
        items = (
            await BaseIngredient.find(with_children=True)
            .skip(skip)
            .limit(limit)
            .to_list()
        )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            {
                "id": str(item.id),
                "activity_type": item.activity_type,
                "title": item.title,
                "created_at": item.created_at,
            }
            for item in items
        ],
    }


@router.get("/{ingredient_id}")
async def get_ingredient(
    ingredient_id: str,
    current_admin: User = Depends(get_current_admin),
):
    """Get a single ingredient by ID."""
    try:
        obj_id = PydanticObjectId(ingredient_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ingredient ID",
        )

    ingredient = await BaseIngredient.find_one(
        BaseIngredient.id == obj_id,
        with_children=True,
    )
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )

    return ingredient.model_dump(by_alias=True)


@router.put("/{ingredient_id}")
async def update_ingredient(
    ingredient_id: str,
    data: Dict[str, Any],  # Flexible JSON
    current_admin: User = Depends(get_current_admin),
):
    """
    Update an ingredient.

    Do not allow changing activity_type (would require model migration).
    All other fields can be updated freely.
    """
    try:
        obj_id = PydanticObjectId(ingredient_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ingredient ID",
        )

    ingredient = await BaseIngredient.find_one(
        BaseIngredient.id == obj_id,
        with_children=True,
    )
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )

    # Prevent changing the type
    if "activity_type" in data and data["activity_type"] != ingredient.activity_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change activity_type after creation",
        )

    # Update fields
    for key, value in data.items():
        if key not in ("activity_type", "id", "_id", "created_at"):
            setattr(ingredient, key, value)

    await ingredient.save()

    return {
        "id": str(ingredient.id),
        "activity_type": ingredient.activity_type,
        "title": ingredient.title,
    }


@router.delete("/{ingredient_id}")
async def delete_ingredient(
    ingredient_id: str,
    current_admin: User = Depends(get_current_admin),
):
    """Delete an ingredient."""
    try:
        obj_id = PydanticObjectId(ingredient_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ingredient ID",
        )

    ingredient = await BaseIngredient.find_one(
        BaseIngredient.id == obj_id,
        with_children=True,
    )
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )

    await ingredient.delete()

    return {"deleted": True}


@router.post("/{ingredient_id}/upload")
async def upload_media(
    ingredient_id: str,
    media_field: str = Query(...),  # e.g. "audio_url", "image_url"
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin),
    media_service: MediaUploadService = Depends(get_media_upload_service),
    storage_service=Depends(get_storage_service),
):
    """
    Upload a media file for an ingredient.

    The file is uploaded to Azure Blob Storage, and the blob path is
    stored in the specified field (audio_url, image_url, etc).

    A signed SAS URL is returned so the admin can preview the upload.

    Args:
        ingredient_id: MongoDB ingredient ID
        media_field: Field name (audio_url, image_url, gif_url, icon_url)
        file: Uploaded file (multipart/form-data)

    Returns:
        {
          "blob_path": "audio/audio_507f1f77bcf86cd799439011.mp3",
          "signed_url": "https://account.blob.core.windows.net/...?sv=...&sig=..."
        }
    """
    # Validate ingredient exists
    try:
        obj_id = PydanticObjectId(ingredient_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ingredient ID",
        )

    ingredient = await BaseIngredient.find_one(
        BaseIngredient.id == obj_id,
        with_children=True,
    )
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )

    # Map field name to file extension
    filename = file.filename or "file"
    ext = "".join(Path(filename).suffixes)  # e.g. ".mp3", ".jpg"
    if not ext:
        ext = ".bin"

    # Read file content
    content = await file.read()

    # Upload to Azure (or local fallback)
    blob_path = await media_service.upload_file(
        file_bytes=content,
        field_name=media_field,
        document_id=str(ingredient.id),
        file_extension=ext,
    )

    # Update the ingredient with the blob path
    setattr(ingredient, media_field, blob_path)
    await ingredient.save()

    # Generate signed URL for preview
    signed_data = await storage_service.sign_media_fields({media_field: blob_path})
    signed_url = signed_data.get(media_field, blob_path)

    return {
        "blob_path": blob_path,
        "signed_url": signed_url,
    }
