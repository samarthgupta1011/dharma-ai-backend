# Dharma AI — Backend

> **Hindu spirituality for the rational mind.**
> A FastAPI backend serving a React Native mobile app with AI-personalised spiritual recipes, Panchang data, and progressive user engagement.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Structure](#2-project-structure)
3. [API Reference](#3-api-reference)
4. [Local Development](#4-local-development)
5. [Database Seeding](#5-database-seeding)
6. [Deployment to Azure](#6-deployment-to-azure)
7. [Environment Variables](#7-environment-variables)
8. [AI Engine Strategy Pattern](#8-ai-engine-strategy-pattern)
9. [Security Model](#9-security-model)

---

## 1. Architecture Overview

```
React Native App
       │  HTTPS
       ▼
Azure Container Apps  ←──────────────────────────────────────┐
  ┌─────────────────────────────────────────────────────────┐ │
  │  FastAPI (Python 3.12)                                  │ │
  │  ┌──────────────────────────────────────────────────┐   │ │
  │  │  Routes: /auth  /users  /recipe  /cosmic         │   │ │
  │  │          /stories  /metadata                     │   │ │
  │  └──────────────────────────────────────────────────┘   │ │
  │  ┌──────────────┐   ┌───────────────────────────────┐   │ │
  │  │ Beanie ODM   │   │ AI Engine (Strategy Pattern)  │   │ │
  │  │ (Motor async)│   │  MockAIEngine (dev)           │   │ │
  │  └──────┬───────┘   │  ClaudeAIEngine (prod)        │   │ │
  │         │           └───────────────────────────────┘   │ │
  └─────────┼───────────────────────────────────────────────┘ │
            │                                                   │
            ▼                                                   │
  Azure Cosmos DB                           Azure Key Vault ────┘
  (API for MongoDB)                    (Managed Identity fetch)
            │
  Azure Blob Storage
  (Media: GIFs, Audio)
```

### Key Architectural Decisions

| Decision | Rationale |
|---|---|
| **FastAPI** | Native async support, auto OpenAPI docs, excellent DI system, Python type hints |
| **Beanie / Motor** | Async ODM for MongoDB. Pydantic v2 models mean one schema for DB + API validation |
| **Polymorphic ingredients** | All activity types in one collection enables cross-type queries and simplifies the AI matching layer |
| **Strategy Pattern for AI** | Swap `MockAIEngine → ClaudeAIEngine` with a single line change, zero route rewrites |
| **Azure Managed Identity** | No credentials in code or environment variables in production. Eliminates an entire class of secrets-management bugs |
| **`GET /metadata/configs`** | Single source of truth for enums. Frontend never drifts out of sync with backend enum additions |

---

## 2. Project Structure

```
dharma-ai-backend/
├── app/
│   ├── main.py                   # FastAPI factory, lifespan, CORS, router mount
│   ├── api/
│   │   ├── dependencies.py       # get_current_user (JWT), get_ai_engine (DI)
│   │   └── routes/
│   │       ├── auth.py           # POST /auth/request-otp, /auth/verify-otp
│   │       ├── users.py          # GET/PUT /users/me, POST /users/me/streak/increment
│   │       ├── recipe.py         # GET /recipe
│   │       ├── cosmic.py         # GET /cosmic
│   │       ├── stories.py        # GET /stories/shuffle
│   │       └── metadata.py       # GET /metadata/configs
│   ├── core/
│   │   ├── config.py             # Pydantic BaseSettings + Azure Key Vault resolver
│   │   └── security.py           # JWT create / decode
│   ├── models/
│   │   ├── user.py               # User document + UserStats embedded doc
│   │   ├── ingredients.py        # BaseIngredient + 6 polymorphic subclasses
│   │   └── panchang.py           # DailyPanchang document
│   └── services/
│       └── ai_service.py         # AIEngine ABC + MockAIEngine
├── scripts/
│   └── seed_data.py              # Populates local DB with sample data
├── .env.example                  # Variable reference — copy to .env
├── docker-compose.yml            # Local dev: MongoDB + API with hot-reload
├── Dockerfile                    # Multi-stage production image
├── requirements.txt
└── README.md
```

---

## 3. API Reference

All endpoints are available via interactive docs at `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc` (ReDoc) when the server is running.

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/request-otp` | None | Send OTP to mobile number |
| `POST` | `/auth/verify-otp` | None | Verify OTP, get JWT + `is_new_user` flag |

**Mock OTP:** In local mode the OTP is always `123456`.

### Users

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/users/me` | JWT | Fetch authenticated user's profile |
| `PUT` | `/users/me` | JWT | Update profile fields (partial update) |
| `POST` | `/users/me/streak/increment` | JWT | Record today's activity, update streak |

### Content

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/recipe?mood=anxious&feelings=...` | JWT | AI-personalised ingredient recipe |
| `GET` | `/cosmic?city=Mumbai&date=2025-01-14` | None | Panchang for city + date |
| `GET` | `/stories/shuffle?count=3` | None | Random story selection |
| `GET` | `/metadata/configs` | None | All enums for frontend sync |
| `GET` | `/health` | None | Liveness probe |

### Example: Full Auth + Recipe Flow

```bash
# 1. Request OTP
curl -X POST http://localhost:8000/auth/request-otp \
  -H "Content-Type: application/json" \
  -d '{"mobile": "+919876543210"}'

# 2. Verify OTP (use 123456 in dev mode)
curl -X POST http://localhost:8000/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"mobile": "+919876543210", "otp": "123456"}'
# → { "access_token": "eyJ...", "is_new_user": true }

# 3. Use the token to get a personalised recipe
curl "http://localhost:8000/recipe?mood=anxious&feelings=Work+deadlines+piling+up" \
  -H "Authorization: Bearer eyJ..."
```

---

## 4. Local Development

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 4.x
- Python 3.12+ (optional — only needed for running without Docker)

### Option A — Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/dharma-ai-backend.git
cd dharma-ai-backend

# 2. Create your local environment file
cp .env.example .env
# No changes needed for local development — defaults work out of the box.

# 3. Start MongoDB + API with hot-reload
docker-compose up -d

# 4. Verify the server is running
curl http://localhost:8000/health
# → {"status":"ok","service":"Dharma AI Backend","version":"1.0.0","environment":"local"}

# 5. Seed the database with sample data
docker-compose exec api python -m scripts.seed_data

# 6. Open interactive API docs
open http://localhost:8000/docs
```

**Useful commands:**
```bash
docker-compose logs -f api          # Tail API logs
docker-compose logs -f mongo        # Tail MongoDB logs
docker-compose restart api          # Restart after config changes
docker-compose down -v              # Stop and wipe all data
```

### Option B — Bare Metal (No Docker)

```bash
# 1. Install MongoDB locally or use Docker for just the DB:
docker run -d -p 27017:27017 --name dharma_mongo mongo:7.0

# 2. Create a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env if needed (defaults point to localhost:27017)

# 5. Start the server with hot-reload
uvicorn app.main:app --reload --port 8000

# 6. Seed the database
python -m scripts.seed_data
```

### How `APP_ENV=local` Bypasses Azure

The `get_mongodb_url()` method in `app/core/config.py` checks `APP_ENV`:

```python
def get_mongodb_url(self) -> str:
    if self.APP_ENV == AppEnvironment.LOCAL:
        return self.MONGODB_URL   # ← Plain env var, no Azure calls

    # Production path: DefaultAzureCredential → Key Vault → Cosmos DB URI
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
    ...
```

The Azure SDK packages (`azure-identity`, `azure-keyvault-secrets`) are installed but **never imported** in local mode.  This means you can develop without any Azure subscription or credentials.

---

## 5. Database Seeding

The seed script (`scripts/seed_data.py`) inserts:

| Collection | Documents inserted |
|---|---|
| `ingredients` | 6 sample documents (one per `ActivityType`) |
| `panchang` | 14 documents (7 days × 2 cities: Mumbai, Delhi) |

```bash
# Via Docker Compose
docker-compose exec api python -m scripts.seed_data

# Bare metal
python -m scripts.seed_data

# Against a remote database
MONGODB_URL="mongodb+srv://..." python -m scripts.seed_data
```

The script is **idempotent** — re-running it skips existing documents without creating duplicates.

---

## 6. Deployment to Azure

### Prerequisites

```bash
# Install the Azure CLI
brew install azure-cli          # macOS
# or: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli

az login
az extension add --name containerapp
```

### Step 1 — Create Azure Resources

```bash
# Variables — customise these
RESOURCE_GROUP="dharma-rg"
LOCATION="eastus"
ACR_NAME="dharmacr"                          # Must be globally unique
CONTAINER_APP_ENV="dharma-env"
CONTAINER_APP_NAME="dharma-api"
KEYVAULT_NAME="dharma-kv"
COSMOS_ACCOUNT="dharma-cosmos"

# Resource Group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Azure Container Registry
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled false          # We use Managed Identity, not admin credentials

# Azure Key Vault
az keyvault create \
  --resource-group $RESOURCE_GROUP \
  --name $KEYVAULT_NAME \
  --location $LOCATION

# Azure Cosmos DB (API for MongoDB)
az cosmosdb create \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT \
  --kind MongoDB \
  --server-version 7.0 \
  --default-consistency-level Session

# Store the Cosmos DB connection string in Key Vault
COSMOS_CONN=$(az cosmosdb keys list \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT \
  --type connection-strings \
  --query "connectionStrings[0].connectionString" -o tsv)

az keyvault secret set \
  --vault-name $KEYVAULT_NAME \
  --name "cosmos-db-connection-string" \
  --value "$COSMOS_CONN"

# Container Apps Environment
az containerapp env create \
  --resource-group $RESOURCE_GROUP \
  --name $CONTAINER_APP_ENV \
  --location $LOCATION
```

### Step 2 — Build and Push Docker Image

```bash
# Build locally and push to ACR using ACR Tasks (no local Docker daemon needed)
az acr build \
  --registry $ACR_NAME \
  --image dharma-api:latest \
  .
```

### Step 3 — Deploy to Azure Container Apps

```bash
az containerapp create \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $CONTAINER_APP_ENV \
  --image "$ACR_NAME.azurecr.io/dharma-api:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 10 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --env-vars \
      APP_ENV=production \
      DATABASE_NAME=dharma_db \
      AZURE_KEY_VAULT_URL="https://$KEYVAULT_NAME.vault.azure.net/" \
      COSMOS_DB_SECRET_NAME=cosmos-db-connection-string \
      JWT_SECRET_KEY=secretref:jwt-secret-key \   # ← Stored in Container App secrets
      JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

### Step 4 — Assign Managed Identity

```bash
# Enable System-Assigned Managed Identity on the Container App
az containerapp identity assign \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --system-assigned

# Get the identity's Principal ID
PRINCIPAL_ID=$(az containerapp identity show \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

# Grant the identity "Key Vault Secrets User" role
# (allows reading secrets, not listing/managing them — principle of least privilege)
KEYVAULT_ID=$(az keyvault show \
  --name $KEYVAULT_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Key Vault Secrets User" \
  --scope $KEYVAULT_ID

# Grant the identity "Cosmos DB Account Reader Role"
# (allows the app to verify DB access, though connection is via the URI in Key Vault)
COSMOS_ID=$(az cosmosdb show \
  --name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Cosmos DB Account Reader Role" \
  --scope $COSMOS_ID

echo "✅ Managed Identity configured. The app will authenticate to Azure without any credentials in code."
```

### Step 5 — Store JWT Secret in Container Apps

```bash
# Store the JWT signing key as a Container App secret (encrypted at rest)
JWT_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

az containerapp secret set \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --secrets jwt-secret-key="$JWT_KEY"

echo "JWT_SECRET_KEY stored as Container App secret."
```

### Step 6 — Verify Deployment

```bash
# Get the Container App FQDN
APP_URL=$(az containerapp show \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "properties.configuration.ingress.fqdn" -o tsv)

curl "https://$APP_URL/health"
# → {"status":"ok","environment":"production",...}
```

### Continuous Deployment (CI/CD)

For GitHub Actions-based CI/CD, add the following workflow:

```yaml
# .github/workflows/deploy.yml
name: Deploy to Azure Container Apps
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      - name: Build and push image
        run: |
          az acr build \
            --registry ${{ vars.ACR_NAME }} \
            --image dharma-api:${{ github.sha }} \
            .
      - name: Deploy new revision
        run: |
          az containerapp update \
            --name ${{ vars.CONTAINER_APP_NAME }} \
            --resource-group ${{ vars.RESOURCE_GROUP }} \
            --image "${{ vars.ACR_NAME }}.azurecr.io/dharma-api:${{ github.sha }}"
```

---

## 7. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_ENV` | No | `local` | `local` or `production` |
| `APP_NAME` | No | `Dharma AI Backend` | Shown in API docs |
| `APP_VERSION` | No | `1.0.0` | Shown in `/health` and docs |
| `DEBUG` | No | `false` | Enables verbose logging |
| `MONGODB_URL` | Local only | `mongodb://localhost:27017` | Ignored in production |
| `DATABASE_NAME` | No | `dharma_db` | MongoDB database name |
| `JWT_SECRET_KEY` | **Yes** | *(weak dev default)* | HS256 signing key — **change in prod** |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `10080` | Token TTL (7 days) |
| `AZURE_KEY_VAULT_URL` | Prod only | `""` | Key Vault URI |
| `COSMOS_DB_SECRET_NAME` | Prod only | `cosmos-db-connection-string` | Secret name in Key Vault |
| `AZURE_STORAGE_ACCOUNT_URL` | Prod only | `""` | Blob Storage URL |
| `AZURE_STORAGE_CONTAINER` | No | `dharma-media` | Blob container name |
| `ALLOWED_ORIGINS` | No | `["*"]` | CORS allow-list |

---

## 8. AI Engine Strategy Pattern

The `AIEngine` abstract base class decouples the personalisation logic from the route handler:

```
app/api/routes/recipe.py          app/api/dependencies.py
        │                                  │
        │  Depends(get_ai_engine)           │  returns MockAIEngine()
        └──────────────────────────────────►│  (swap to ClaudeAIEngine here)
                                           │
                               app/services/ai_service.py
                                 ┌──────────────────────┐
                                 │  AIEngine (ABC)       │
                                 │  + generate_recipe()  │
                                 └──────────┬───────────┘
                                            │
                               ┌────────────┴─────────────┐
                               │                           │
                    MockAIEngine               ClaudeAIEngine (future)
                  (one of each type           (sends mood+feelings to
                   from the DB)                Claude API, returns
                                               matched ingredient IDs)
```

### Implementing a Real AI Engine

```python
# app/services/ai_service.py

from anthropic import AsyncAnthropic

class ClaudeAIEngine(AIEngine):
    def __init__(self) -> None:
        self._client = AsyncAnthropic()  # Reads ANTHROPIC_API_KEY from env

    async def generate_recipe(self, mood: str, feelings: str) -> List[BaseIngredient]:
        # 1. Fetch all ingredient titles + tags from DB for context
        # 2. Build a structured prompt asking Claude to select the best matches
        # 3. Parse Claude's response (tool_use / structured output)
        # 4. Fetch and return the selected Beanie documents
        ...
```

Then in `app/api/dependencies.py`:
```python
def get_ai_engine() -> AIEngine:
    return ClaudeAIEngine()  # ← one-line swap
```

---

## 9. Security Model

### Authentication Flow

```
Mobile App                    Backend                        MongoDB
    │                            │                               │
    │── POST /auth/request-otp ──►│                               │
    │                            │── (Send OTP via SMS) ─────────►│
    │◄── { "status": "sent" } ───│                               │
    │                            │                               │
    │── POST /auth/verify-otp ───►│                               │
    │   { mobile, otp: "123456" } │── find_one({ mobile }) ───────►│
    │                            │◄── User or null ───────────────│
    │                            │── (create User if null) ───────►│
    │◄── { access_token, is_new_user }                            │
```

### JWT Structure

```json
{
  "sub": "60d5ecb8f7c3a4e5f0a1b2c3",   // MongoDB ObjectId of User
  "iat": 1720000000,                    // Issued at (Unix timestamp)
  "exp": 1720604800                     // Expires 7 days later
}
```

### Production Secrets — Zero Hardcoding

| Secret | How it's managed |
|---|---|
| Cosmos DB connection string | Azure Key Vault secret, fetched at startup via Managed Identity |
| JWT signing key | Azure Container Apps secret (encrypted at rest), injected as env var |
| OTP values | Redis (Azure Cache for Redis) with 10-minute TTL — never persisted to DB |

The application process **never handles** raw Azure credentials.  `DefaultAzureCredential` uses the Container App's system-assigned Managed Identity token endpoint (available at `http://169.254.169.254/metadata/identity/...`) which Azure infrastructure manages entirely.
