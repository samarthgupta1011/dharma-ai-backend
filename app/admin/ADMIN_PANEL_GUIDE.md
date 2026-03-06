# Admin Panel

REST API for managing spiritual ingredients (Gita verses, yoga poses, breathing techniques, mantras, stories, good deeds).

## Setup

1. **Enable admin role** via MongoDB:
```bash
mongosh mongodb://localhost:27017/dharma_db
db.users.updateOne({ mobile: "+919876543210" }, { $set: { is_admin: true } }, { upsert: true })
```

2. **Get JWT token** via OTP login:
```bash
curl -X POST http://localhost:8000/auth/request-otp \
  -d '{"mobile": "+919876543210"}'

curl -X POST http://localhost:8000/auth/verify-otp \
  -d '{"mobile": "+919876543210", "otp": "111111"}'
# Returns: { "access_token": "..." }
```

## Endpoints

All endpoints require `Authorization: Bearer <token>` header.

### Get Form Schema
Returns template for all ingredient types (required/optional fields, media fields).
```
GET /admin/ingredients/form-schema
```

### Create Ingredient
```
POST /admin/ingredients
{
  "activity_type": "GITA",
  "title": "Chapter 2, Verse 47",
  "why": "Scientific context...",
  "sanskrit_text": "...",
  "transliteration": "...",
  "english_translation": "...",
  "commentary": "..."
}
```
Auto-populated: `created_at`, empty `tags` dict, empty media URLs.

### List Ingredients
```
GET /admin/ingredients?skip=0&limit=20&activity_type=GITA
```

### Get Single
```
GET /admin/ingredients/{id}
```

### Update
```
PUT /admin/ingredients/{id}
{ "commentary": "Updated..." }
```
Cannot change `activity_type` after creation.

### Delete
```
DELETE /admin/ingredients/{id}
```

### Upload Media
```
POST /admin/ingredients/{id}/upload
Content-Type: multipart/form-data

media_field=audio_url
file=@verse.mp3
```
Returns:
```json
{
  "blob_path": "audio/audio_507f1f77bcf86cd799439011.mp3",
  "signed_url": "https://...?sv=2024-11-05&sig=..."
}
```

## Ingredient Types

| Type | Required | Optional | Media |
|------|----------|----------|-------|
| GITA | title, why | emoji, subtitle, duration_mins, location, short_descp, chapter, verse_number, sanskrit_text, transliteration, english_translation, commentary, tags, icon_url | audio_url, icon_url |
| YOGA | title, why | emoji, subtitle, duration_mins, location, short_descp, icon_url, gif_url, steps, anatomical_focus, tags | gif_url, icon_url |
| BREATHING | title, why | emoji, subtitle, duration_mins, location, short_descp, icon_url, audio_url, duration_seconds, pattern, animation, tags | audio_url, icon_url |
| MANTRA | title, why | emoji, subtitle, duration_mins, location, short_descp, icon_url, audio_url, mantra_text, frequency_hz, tags | audio_url, icon_url |
| PUNYA | title, why | emoji, subtitle, duration_mins, location, short_descp, activity, icon_url, tags | icon_url |
| STORY | title, why | emoji, subtitle, duration_mins, location, short_descp, icon_url, image_url, story_text, scripture_source, tags | image_url, icon_url |

## Key Features

- **Dynamic form schema**: Frontend gets type-specific fields from `/form-schema`
- **Type dropdown**: Admin selects ingredient type, form populates accordingly
- **Auto-filled fields**: `created_at`, empty `tags`, empty media URLs
- **Media upload**: Automatic path generation `{field}/{field}_{id}.{ext}`
- **Flexible JSON**: No validation—admin can add custom fields
- **JWT auth**: Reuses OTP login flow, checks `is_admin` role

## Quick Workflow

1. `GET /admin/ingredients/form-schema` → Admin selects type
2. Fill form, `POST /admin/ingredients` → Get ingredient ID
3. `POST /admin/ingredients/{id}/upload?media_field=audio_url` → Upload file
4. Done! Field auto-updated with blob path

## Docs

- OpenAPI: http://localhost:8000/docs
- Interactive testing: Use "Try it out" in Swagger UI

