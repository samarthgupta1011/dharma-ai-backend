# Dharma AI — Backend

> **Hindu spirituality for the rational mind.**
> A FastAPI backend serving a React Native mobile app with AI-personalised spiritual recipes, Panchang data, and progressive user engagement.

---

## Table of Contents

1. [API Reference](#3-api-reference)
2. [Local Development](#4-local-development)
3. [Database Seeding](#5-database-seeding)
4. [Deployment to Azure](#6-deployment-to-azure)
5. [Environment Variables](#7-environment-variables)
6. [AI Engine Strategy Pattern](#8-ai-engine-strategy-pattern)
7. [Security Model](#9-security-model)

---

## 1. API Reference

All endpoints are available via interactive docs at `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc` (ReDoc) when the server is running.

---

## 2. Local Development

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 4.x
- Python 3.12+ (optional — only needed for running without Docker)

### Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/dharma-ai-backend.git
cd dharma-ai-backend

# 2. Copy environment template and update with your local values
cp .env.example .env
# Edit .env if needed (defaults work out of the box for local dev)

# 3. Start MongoDB 6.0 + API with hot-reload
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
docker-compose logs -f api        # Tail API logs
docker-compose logs -f mongo      # Tail MongoDB logs
docker-compose restart api        # Restart after config changes
docker-compose down -v            # Stop and wipe all data
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

## 3. Database Seeding

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

# Against a remote Cosmos DB (e.g. staging) — pass its connection string directly
MONGODB_URL="mongodb://accountname:key@account.mongo.cosmos.azure.com:10255/dharma_db?ssl=true&replicaSet=globaldb&retrywrites=false" \
  python -m scripts.seed_data
```

The script is **idempotent** — re-running it skips existing documents without creating duplicates.

---

## 4. Deployment to Azure

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

# Store the JWT secret in Key Vault (generated at runtime by the app)
JWT_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

az keyvault secret set \
  --vault-name $KEYVAULT_NAME \
  --name "jwt-secret-key" \
  --value "$JWT_KEY"

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

### Step 3 — Create Managed Identity

```bash
# Create a user-assigned managed identity
# This identity will authenticate the Container App to Azure Key Vault
MANAGED_IDENTITY="dharma-env-umsi"

az identity create \
  --name $MANAGED_IDENTITY \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Get its client ID (needed for Container App deployment)
UMSI_CLIENT_ID=$(az identity show \
  --name $MANAGED_IDENTITY \
  --resource-group $RESOURCE_GROUP \
  --query clientId -o tsv)

echo "✅ Managed Identity created: $MANAGED_IDENTITY"
echo "   Client ID: $UMSI_CLIENT_ID"
```

### Step 4 — Deploy Container App with prod.env

```bash
# Create the Container App and load all configuration from prod.env
# Only AZURE_CLIENT_ID is set separately (instance-specific UMSI reference)

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
  --user-assigned $MANAGED_IDENTITY \
  --env-vars-from-file prod.env \
  --set-env-vars AZURE_CLIENT_ID="$UMSI_CLIENT_ID"

echo "✅ Container App created with prod.env + AZURE_CLIENT_ID"
```

### Step 5 — Configure RBAC (Managed Identity Permissions)

```bash
# Grant the UMSI permissions to access Azure Key Vault and Cosmos DB

PRINCIPAL_ID=$(az identity show \
  --name $MANAGED_IDENTITY \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

# Grant "Key Vault Secrets User" — allows reading secrets from AKV
KEYVAULT_ID=$(az keyvault show \
  --name $KEYVAULT_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Key Vault Secrets User" \
  --scope $KEYVAULT_ID

# Grant "Cosmos DB Account Reader Role"
COSMOS_ID=$(az cosmosdb show \
  --name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Cosmos DB Account Reader Role" \
  --scope $COSMOS_ID

# Grant "Storage Blob Delegator" — allows get_user_delegation_key() for SAS URL generation
STORAGE_ACCOUNT="dharmastorage"   # Update with your storage account name
STORAGE_ID=$(az storage account show \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Storage Blob Delegator" \
  --scope $STORAGE_ID

# Grant "Storage Blob Data Reader" — allows the generated SAS to grant read access to blobs
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Storage Blob Data Reader" \
  --scope "$STORAGE_ID/blobServices/default/containers/dharma-media"

echo "✅ RBAC configured — UMSI can read from AKV, Cosmos DB, and generate Blob SAS URLs"
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

# View logs if health check fails
az containerapp logs show \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --follow | head -50
```

### Step 7 — Update Existing Deployment

```bash
# Build and push with unique tag (prevents caching issues)
IMAGE_TAG=$(git rev-parse --short HEAD)-$(date +%s)
az acr build --registry dharmacr --platform linux/amd64 --image dharma-api:${IMAGE_TAG} .

# Parse env vars with proper formatting
ENV_VARS=$(grep -v '^#' app/config/prod.env | grep -v '^$')
UMSI_CLIENT_ID=$(az identity show --name dharma-env-umsi --resource-group dharma-rg --query clientId -o tsv)

# Deploy (convert newlines to spaces for proper parsing)
az containerapp update \
  --name dharma-api \
  --resource-group dharma-rg \
  --image dharmacr.azurecr.io/dharma-api:${IMAGE_TAG} \
  --set-env-vars $(echo "${ENV_VARS}" | tr '\n' ' ') AZURE_CLIENT_ID=${UMSI_CLIENT_ID}
```

### Continuous Deployment (CI/CD)

GitHub Actions workflow for automatic deployment on push to `main`:

```yaml
# .github/workflows/deploy.yml
name: Deploy to Azure
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
      
      - name: Build and push
        run: |
          az acr build \
            --registry ${{ vars.ACR_NAME }} \
            --platform linux/amd64 \
            --image dharma-api:${{ github.sha }} .
      
      - name: Deploy
        run: |
          ENV_VARS=$(grep -v '^#' app/config/prod.env | grep -v '^$')
          UMSI_ID=$(az identity show --name dharma-env-umsi --resource-group ${{ vars.RESOURCE_GROUP }} --query clientId -o tsv)
          az containerapp update \
            --name ${{ vars.CONTAINER_APP_NAME }} \
            --resource-group ${{ vars.RESOURCE_GROUP }} \
            --image "${{ vars.ACR_NAME }}.azurecr.io/dharma-api:${{ github.sha }}" \
            --set-env-vars $(echo "${ENV_VARS}" | tr '\n' ' ') AZURE_CLIENT_ID=${UMSI_ID}
```

---

## 5. Environment Variables & Configuration

Configuration is split into **three sources** depending on the environment. This eliminates confusion about "where does this variable come from?"

### Configuration Architecture

```
┌──────────────────────────────────────┐
│   LOCAL DEVELOPMENT (APP_ENV=local)  │
├──────────────────────────────────────┤
│  .env (copy of .env.example)         │
│  ├─ APP_ENV=local                    │
│  ├─ MONGODB_URL (local mongo)        │
│  ├─ JWT_SECRET_KEY (weak dev key)    │
│  └─ DEBUG=true                       │
│                                      │
│  Loaded by: docker-compose           │
│  Secrets from: .env (local file)     │
│  No Azure SDK calls                  │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ PRODUCTION (APP_ENV=production)      │
├──────────────────────────────────────┤
│  prod.env + Azure Key Vault          │
│  ├─ prod.env (config, safe to git)  │
│  │  ├─ APP_ENV=production            │
│  │  ├─ AZURE_KEY_VAULT_URL           │
│  │  ├─ COSMOS_DB_SECRET_NAME         │
│  │  ├─ JWT_SECRET_NAME               │
│  │  └─ ALLOWED_ORIGINS               │
│  │                                   │
│  ├─ Azure Key Vault (secrets only)   │
│  │  ├─ cosmos-db-connection-string   │
│  │  └─ jwt-secret-key                │
│  │                                   │
│  ├─ Container App (Managed Identity) │
│  │  └─ AZURE_CLIENT_ID (UMSI ref)    │
│  │                                   │
│  Loaded by: Container App at startup │
│  Secrets fetched: Key Vault          │
│  Auth: Managed Identity              │
└──────────────────────────────────────┘
```

### Local Development (`.env`)

Used by `docker-compose up`. Copy `.env.example` to `.env` for local development. This file is **ignored by git** and contains no secrets.

| Variable | Value | Purpose |
|----------|-------|---------|
| `APP_ENV` | `local` | Tells app to skip Azure SDK |
| `MONGODB_URL` | `mongodb://localhost:27017` | Local MongoDB in docker-compose |
| `DATABASE_NAME` | `dharma_db` | DB name (same for local + prod) |
| `JWT_SECRET_KEY` | `change-me-...` | Weak dev key (OK for testing) |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | 7 days |
| `DEBUG` | `true` | Enable verbose logging |
| `ALLOWED_ORIGINS` | `["*"]` | Allow all origins (unsafe for prod) |

**Usage:**
```bash
cp .env.example .env
docker-compose up
```

### Production Configuration (`prod.env`)

Deployed to Azure Container Apps. This file is **safe to commit to git** — it contains only configuration, no secrets.

| Variable | Value | Purpose |
|----------|-------|---------|
| `APP_ENV` | `production` | Tells app to load secrets from AKV |
| `AZURE_KEY_VAULT_URL` | `https://dharma-kv.vault.azure.net/` | AKV endpoint |
| `COSMOS_DB_SECRET_NAME` | `cosmos-db-connection-string` | Secret name (value fetched from AKV) |
| `JWT_SECRET_NAME` | `jwt-secret-key` | Secret name (value fetched from AKV) |
| `AZURE_STORAGE_ACCOUNT_URL` | `https://<account>.blob.core.windows.net` | Blob storage URL |
| `AZURE_STORAGE_CONTAINER` | `dharma-media` | Blob container name |
| `AZURE_STORAGE_SAS_EXPIRY_MINUTES` | `60` | Lifetime (minutes) for generated Blob SAS URLs |
| `DEBUG` | `false` | Disable verbose logging |
| `ALLOWED_ORIGINS` | `["https://dharma-app.example.com"]` | Restrict to your domain |

**Note:** `AZURE_CLIENT_ID` is **not** in `prod.env` — it ties to a specific Managed Identity and is set separately during Container App deployment.

### Secrets in Azure Key Vault (Production Only)

These are fetched at startup by `@model_validator` in [config.py](app/core/config.py):

| Secret Name | Value | Fetched into |
|-------------|-------|--------------|
| `cosmos-db-connection-string` | `mongodb://accountname:key@account.mongo.cosmos.azure.com:10255/...` | `MONGODB_URL` |
| `jwt-secret-key` | `<256-bit hex string>` | `JWT_SECRET_KEY` |

**Never commit real connection strings or keys to git.**

### How Configuration is Loaded

**Local Mode:**
```python
# .env (copy of .env.example)
#   ↓
# Pydantic reads all vars
#   ↓
# No AKV calls → Ready
```

**Production Mode:**
```python
# prod.env → Container App env vars set
#   ↓
# Pydantic reads all vars
#   ↓
# @model_validator(mode="after") checks APP_ENV == PRODUCTION
#   ↓
# DefaultAzureCredential (uses AZURE_CLIENT_ID)
#   ↓
# SecretClient fetches from AKV
#   ↓
# Overwrites MONGODB_URL and JWT_SECRET_KEY
#   ↓
# Ready
```

---

## 6. AI Engine Strategy Pattern

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

## 7. Security Model

### Authentication Flow

```
Mobile App                    Backend                        Cosmos DB
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
  "sub": "60d5ecb8f7c3a4e5f0a1b2c3",   // Cosmos DB document _id of the User
  "iat": 1720000000,                    // Issued at (Unix timestamp)
  "exp": 1720604800                     // Expires 7 days later
}
```

### Production Secrets — Zero Hardcoding

| Secret | How it's managed |
|---|---|
| Cosmos DB connection string | Azure Key Vault secret, fetched at startup via Managed Identity |
| JWT signing key | Azure Key Vault secret, fetched at startup via Managed Identity |
| OTP values | Redis (Azure Cache for Redis) with 10-minute TTL — never persisted to DB |

The application process **never handles** raw Azure credentials. `DefaultAzureCredential` uses the Container App's Managed Identity token endpoint (available at `http://169.254.169.254/metadata/identity/...`) which Azure infrastructure manages entirely. Both secrets are fetched from Key Vault during the `@model_validator` phase in `config.py`, before the app starts serving requests.
