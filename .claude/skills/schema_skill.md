# Skill: Application Schema Reference

## Purpose
Document the current schema of all models so Claude can make changes that don't break existing code, seed data, or API routes.

---

## Ingredients (`ingredients` collection)

### Polymorphic Pattern
- **ODM**: Beanie with `is_root = True` on `BaseIngredient`
- **Discriminator**: `_class_id` field auto-injected by Beanie — maps to Python subclass
- **All 7 types live in ONE collection** (`ingredients`)
- **Pydantic discriminator**: `activity_type` field uses `Literal[ActivityType.X]` on each subclass for OpenAPI schema generation

### ActivityType Enum
```
YOGA | GITA | BREATHING | MANTRA | PUNYA | STORY | REFLECTION
```

### Embedded Pydantic Models (used in AI-generated responses)
| Model | Fields | Used By |
|-------|--------|---------|
| `DeeperInsight` | `emoji: str`, `title: str`, `inference: str` | `GitaVerse.deeper_insights` |
| `ImpactPointer` | `emoji: str`, `point: str` | `Punya.ai_impact`, `Breathing.ai_impact` |
| `ReflectionQuestion` | `emoji: str`, `question: str` | `Reflection.reflection_questions` |

### BaseIngredient (common fields — all types inherit these)
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `activity_type` | `ActivityType` | — | Overridden with `Literal[...]` in subclasses |
| `title` | `str` | required | Short human-readable title |
| `emoji` | `str` | `""` | Decorative emoji (safe, positive only) |
| `subtitle` | `str` | `""` | Secondary display text below title |
| `why` | `str` | required | Science/history rationale (core UX field) |
| `duration_mins` | `Optional[int]` | `None` | Read or practice duration in minutes |
| `location` | `Optional[str]` | `None` | `"work"`, `"home"`, or `"anywhere"` |
| `short_descp` | `str` | `""` | Brief context passed to AI for activity selection (~15 words) |
| `tags` | `Dict[str, float]` | `{}` | Keyword → relevance score for AI matching |
| `icon_url` | `str` | `""` | Azure Blob Storage URL |
| `created_at` | `datetime` | `utcnow()` | UTC timestamp |

### GitaVerse (`activity_type = GITA`)
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `chapter` | `Optional[int]` | `None` | Bhagavad Gita chapter (1-18) |
| `verse_number` | `Optional[int]` | `None` | Verse within chapter |
| `deeper_insights_title` | `Optional[str]` | `None` | AI-generated evocative one-liner |
| `deeper_insights` | `List[DeeperInsight]` | `[]` | AI-generated: 3 insights with emoji+title+inference |
| `sanskrit_text` | `Optional[str]` | `None` | Original Devanagari |
| `transliteration` | `Optional[str]` | `None` | Roman-script phonetic |
| `english_translation` | `Optional[str]` | `None` | Literal English translation |
| `commentary` | `Optional[str]` | `None` | Commentary linking verse to modern life |
| `audio_url` | `str` | `""` | Azure Blob URL for recitation audio |

### Yoga (`activity_type = YOGA`)
| Field | Type | Default |
|-------|------|---------|
| `gif_url` | `str` | `""` |
| `steps` | `List[str]` | `[]` |
| `anatomical_focus` | `str` | `""` |

### Breathing (`activity_type = BREATHING`)
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `audio_url` | `str` | `""` | |
| `duration_seconds` | `int` | `0` | |
| `pattern` | `str` | `""` | e.g. "4-7-8" |
| `animation` | `Optional[int]` | `None` | Frontend animation enum number |
| `ai_why` | `Optional[str]` | `None` | AI-generated: why this helps (~25 words) |
| `ai_impact` | `Optional[List[ImpactPointer]]` | `None` | AI-generated: 1-3 impact pointers |

### Chanting (`activity_type = MANTRA`)
| Field | Type | Default |
|-------|------|---------|
| `audio_url` | `str` | `""` |
| `mantra_text` | `str` | `""` |
| `frequency_hz` | `float` | `0.0` |

### Punya (`activity_type = PUNYA`)
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `activity` | `str` | `""` | What to do (concrete action) |
| `ai_why` | `Optional[str]` | `None` | AI-generated: why this helps (~25 words) |
| `ai_impact` | `Optional[List[ImpactPointer]]` | `None` | AI-generated: 1-3 impact pointers |

### Story (`activity_type = STORY`)
| Field | Type | Default |
|-------|------|---------|
| `story_text` | `str` | `""` |
| `scripture_source` | `str` | `""` |
| `image_url` | `str` | `""` |

### Reflection (`activity_type = REFLECTION`)
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `reflection_questions` | `List[ReflectionQuestion]` | `[]` | Each has `emoji` + `question` |

---

## User (`users` collection)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `mobile` | `str` | required | Unique indexed, primary login ID |
| `name` | `Optional[str]` | `None` | Filled progressively |
| `email` | `Optional[str]` | `None` | Filled progressively |
| `dob` | `Optional[date]` | `None` | |
| `city` | `Optional[str]` | `None` | |
| `created_at` | `datetime` | `utcnow()` | |
| `stats` | `UserStats` | `UserStats()` | Embedded sub-document |
| `active_refresh_jti` | `Optional[str]` | `None` | Current refresh token JTI |
| `refresh_token_expires_at` | `Optional[datetime]` | `None` | |
| `is_admin` | `bool` | `False` | |

### UserStats (embedded in User)
| Field | Type | Default |
|-------|------|---------|
| `current_streak` | `int` | `0` |
| `longest_streak` | `int` | `0` |
| `last_activity_date` | `Optional[date]` | `None` |

---

## DailyPanchang (`panchang` collection)

Compound unique index on `(date, city)`.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `date` | `date` | required | Indexed |
| `city` | `str` | required | Indexed |
| `tithi` | `str` | required | Lunar day name |
| `tithi_end` | `str` | required | HH:MM format |
| `nakshatra` | `str` | required | Lunar mansion (1 of 27) |
| `nakshatra_end` | `str` | required | HH:MM format |
| `vaar` | `str` | required | Sanskrit weekday |
| `yoga` | `str` | required | Sun+Moon longitude measure (1 of 27) |
| `karana` | `str` | required | Half-tithi (1 of 11) |
| `karana_end` | `str` | required | HH:MM format |
| `paksha` | `str` | required | Shukla (waxing) or Krishna (waning) |
| `inferences` | `List[str]` | `[]` | Evidence-based observations for the day |

---

## When Modifying Any Schema

### Touchpoints to check
1. **Seed data** — `scripts/seed_data.py` — update sample documents if fields are added/removed
2. **API routes** — `app/api/routes/` — check if any route reads/writes the changed field
3. **Admin routes** — `app/admin/routes/` — check admin panel endpoints
4. **OpenAI service** — `app/services/openai_service.py` — if changing `GitaVerse`, `Punya`, `Breathing`, or `Reflection` fields, the AI response parsing and validation may need updating
5. **AI prompts** — `app/prompts/dharma_prompts.py` — if changing field names in AI-overlay fields, the prompt JSON schema must match
6. **Admin guide** — `app/admin/ADMIN_PANEL_GUIDE.md` — update type-specific field documentation

### Guidelines
- **New fields should be `Optional` or have a default** — existing MongoDB documents won't have the field, so a required field with no default will crash on read
- **Beanie polymorphic quirk** — if adding a new `ActivityType`, you must: add to enum, create subclass, and register it in Beanie's `document_models` list in `app/main.py`
- **Tags field affects AI matching** — changes to `tags` structure affect how `ai_service.py` selects ingredients
<!-- TODO: Add stricter validation rules as design solidifies -->
