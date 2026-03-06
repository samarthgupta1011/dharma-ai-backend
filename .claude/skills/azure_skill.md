# Skill: Application & Azure Context

## Purpose
Provide Claude with full application context so it can debug, add features, and make changes without needing repeated input from the developer.

---

## Application Overview
- **Stack**: FastAPI + Beanie ODM + MongoDB (local) / Azure Cosmos DB (prod)
- **Purpose**: Hindu spirituality app — AI-personalised spiritual "recipes" (combinations of yoga, breathing, Gita verses, etc.) based on user mood
- **Design philosophy**: Ground practices in science/history, not faith ("skeptic-friendly")

## Architecture Patterns
- **Strategy pattern for AI services**: `AIEngine` (ABC) in `app/services/ai_service.py` — swap implementations via FastAPI `Depends()` in `app/api/dependencies.py`
- **Strategy pattern for OpenAI**: `BaseOpenAIService` in `app/services/openai_service.py` — `OpenAIService` (real) vs `MockOpenAIService` (dev). Controlled by `ENABLE_OPENAI` env var. Main method: `generate_dharma_recipe(mood, feelings, punya_context, breathing_context)` returns 4-category dict
- **AI prompts in separate file**: `app/prompts/dharma_prompts.py` — `SYSTEM_PROMPT` (guardrails: Hindu-scripture-only, safe emojis, no self-harm encouragement) + `RECIPE_PROMPT_TEMPLATE` (4-category JSON recipe). Edit prompts here without touching service code
- **Polymorphic Beanie documents**: `BaseIngredient` is the collection root with `is_root = True`. All 7 activity types live in one `ingredients` collection, discriminated by `_class_id`
- **Environment-aware config**: `app/config/settings.py` — `APP_ENV=local` skips all Azure SDK calls; `APP_ENV=production` fetches secrets from AKV via Managed Identity

## Key Files
| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app, lifespan, Beanie init |
| `app/config/settings.py` | All env var definitions + AKV loading |
| `app/config/prod.env` | Production env vars (safe to commit, no secrets) |
| `app/models/ingredients.py` | Polymorphic ingredient models |
| `app/models/user.py` | User model + UserStats embedded doc |
| `app/models/panchang.py` | Daily Panchang (Hindu almanac) model |
| `app/services/ai_service.py` | AI engine strategy pattern |
| `app/services/openai_service.py` | OpenAI service strategy pattern |
| `app/prompts/dharma_prompts.py` | AI system prompt (guardrails) + recipe prompt template |
| `app/api/dependencies.py` | FastAPI dependency injection |
| `scripts/seed_data.py` | DB seeding script |
| `docker-compose.yml` | Local dev environment |
| `.github/workflows/deploy.yml` | CI/CD pipeline |

---

## Azure Infrastructure

### Resource Names
| Resource | Name | Resource Group |
|----------|------|----------------|
| Resource Group | `dharma-rg` | — |
| Container Registry (ACR) | `dharmacr` | `dharma-rg` |
| Cosmos DB (MongoDB API) | `dharma-cosmos` | `dharma-rg` |
| Key Vault | `dharma-kv` | `dharma-rg` |
| Container Apps Environment | `dharma-env` | `dharma-rg` |
| Container App | `dharma-api` | `dharma-rg` |
| Managed Identity (UMSI) | `dharma-env-umsi` | `dharma-rg` |
| Storage Account | `dharmastorageacc` | `dharma-rg` |
| Blob Container | `dharma-content` | (in `dharmastorageacc`) |
| Location/Region | `eastus` | — |

### Key Vault Secrets
| Secret Name | What It Holds | Used By |
|-------------|---------------|---------|
| `cosmos-db-connection-string` | Cosmos DB MongoDB connection URI | `MONGODB_URL` at startup |
| `jwt-secret-key` | HS256 JWT signing key (64-char hex) | `JWT_SECRET_KEY` at startup |
| `openai-api-key` | OpenAI API key (`sk-...`) | `OPENAI_API_KEY` at startup (only if `ENABLE_OPENAI=true`) |

### RBAC Assignments (Managed Identity → Resources)
| Role | Scope | Purpose |
|------|-------|---------|
| Key Vault Secrets User | `dharma-kv` | Read secrets (Cosmos DB URI, JWT key, OpenAI key) |
| Cosmos DB Account Reader Role | `dharma-cosmos` | DB access |
| Storage Blob Delegator | `dharmastorageacc` | Generate user-delegation SAS URLs |
| Storage Blob Data Reader | `dharma-content` container | Grant read access via generated SAS |

### Environment Variable Flow
**Local** (`APP_ENV=local`):
- All vars from `.env` file (copied from `.env.example`)
- `docker-compose.yml` overrides `MONGODB_URL` to `mongodb://mongo:27017` (Docker DNS)
- No Azure SDK calls happen at all
- `ENABLE_OPENAI=false` → uses `MockOpenAIService`

**Production** (`APP_ENV=production`):
- Non-secret vars from `prod.env` (loaded via `az containerapp update --env-vars-from-file`)
- `AZURE_CLIENT_ID` set separately at deploy time (instance-specific UMSI ref)
- At startup, `@model_validator` in `settings.py` uses UMSI → AKV to fetch: `MONGODB_URL`, `JWT_SECRET_KEY`, `OPENAI_API_KEY`
- If any AKV fetch fails, app crashes immediately with descriptive error

### CI/CD Pipeline (`.github/workflows/deploy.yml`)
- **Trigger**: push to `main` or manual dispatch
- **Build job**: `az acr build` pushes image tagged with commit SHA + `latest`
- **Deploy job**: requires `production` environment approval, then:
  1. Gets UMSI client ID
  2. Parses `prod.env` into env vars
  3. `az containerapp update` with new image + env vars + `AZURE_CLIENT_ID`
  4. Health check retry loop (30 attempts, 10s apart = 5min timeout)
- **GitHub Secrets needed**: `AZURE_CREDENTIALS` (service principal JSON)
- **GitHub Variables needed**: `ACR_NAME`, `RESOURCE_GROUP`, `CONTAINER_APP_NAME`

---

## Development Workflow
- Local dev: `docker-compose up -d` → MongoDB 6.0 (ARM64 native, Cosmos DB compatible) + FastAPI with hot-reload
- Seeding: `docker-compose exec api python -m scripts.seed_data` (idempotent)
- MongoDB 6.0 locally mirrors Cosmos DB API v6.0 — no functional gap for this codebase
- Admin panel exists at `app/admin/` with OTP auth
<!-- TODO: Add more constraints as design evolves -->
