# Dharma AI — Backend

> Hindu spirituality for the rational mind. A FastAPI backend serving AI-personalised spiritual recipes, Panchang data, and progressive user engagement.

---

## Quick Start

```bash
# Clone and start
git clone https://github.com/your-org/dharma-ai-backend.git
cd dharma-ai-backend
cp .env.example app/config/.env

# Start MongoDB 6.0 + API with hot-reload
docker-compose up -d

# Seed the database
docker-compose exec api python -m scripts.seed_data

# Open interactive API docs
open http://localhost:8000/docs
```

**URLs (local):**
| Endpoint | URL |
|----------|-----|
| Health check | `GET http://localhost:8000/health` |
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |

**Useful commands:**
```bash
docker-compose logs -f api        # Tail API logs
docker-compose restart api        # Restart after config changes
docker-compose down -v            # Stop and wipe all data
```

---

## Database Seeding

```bash
docker-compose exec api python -m scripts.seed_data
```

Inserts sample data into:
| Collection | What |
|------------|------|
| `ingredients` | 6 sample documents (one per `ActivityType`) |
| `panchang` | 14 documents (7 days × 2 cities: Mumbai, Delhi) |

The script is **idempotent** — re-running skips existing documents.

---

## GitHub Actions Pipeline

Push to `main` triggers `.github/workflows/deploy.yml`:

1. **Build**: `az acr build` → pushes image to ACR (tagged with commit SHA + `latest`)
2. **Deploy** (requires `production` environment approval):
   - Parses `app/config/prod.env` for non-secret env vars
   - Sets `AZURE_CLIENT_ID` from UMSI
   - `az containerapp update` deploys new image
   - Health check retry loop (5-min timeout)

GitHub Secrets: `AZURE_CREDENTIALS` (service principal JSON)
GitHub Variables: `ACR_NAME`, `RESOURCE_GROUP`, `CONTAINER_APP_NAME`

---

## Environment Variables

### Local Development (`.env`)

Copy `.env.example` to `app/config/.env`. These are used by `docker-compose up`.

| Variable | Where Set | Purpose | Manual AKV? |
|----------|-----------|---------|-------------|
| `APP_ENV` | `.env` | Set to `local` — skips all Azure SDK calls | No |
| `MONGODB_URL` | `docker-compose.yml` | Overridden to `mongodb://mongo:27017` | No |
| `DATABASE_NAME` | `.env` | DB name (`dharma_db`) | No |
| `JWT_SECRET_KEY` | `.env` | Weak dev signing key | No |
| `JWT_ALGORITHM` | `.env` | `HS256` | No |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `.env` | Token lifetime (default: `10080` = 7 days) | No |
| `DEBUG` | `.env` | `true` for verbose logging | No |
| `ALLOWED_ORIGINS` | `.env` | `["*"]` for local | No |
| `ENABLE_OPENAI` | `.env` | `false` = mock service (no API calls); `true` = real OpenAI | No |
| `OPENAI_API_KEY` | `.env` | Only needed if `ENABLE_OPENAI=true` | No |

### Production (`prod.env` + Azure Key Vault)

`prod.env` is committed to git (no secrets). Secrets are fetched from AKV at startup via Managed Identity.

| Variable | Where Set | Purpose | Manual AKV? |
|----------|-----------|---------|-------------|
| `APP_ENV` | `prod.env` | `production` — enables AKV secret loading | No |
| `DATABASE_NAME` | `prod.env` | `dharma_db` | No |
| `JWT_SECRET_NAME` | `prod.env` | AKV secret name for JWT key | No |
| `JWT_ALGORITHM` | `prod.env` | `HS256` | No |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `prod.env` | `10080` | No |
| `AZURE_KEY_VAULT_URL` | `prod.env` | `https://dharma-kv.vault.azure.net/` | No |
| `COSMOS_DB_SECRET_NAME` | `prod.env` | AKV secret name for Cosmos DB URI | No |
| `AZURE_STORAGE_ACCOUNT_URL` | `prod.env` | Blob storage endpoint | No |
| `AZURE_STORAGE_CONTAINER` | `prod.env` | `dharma-content` | No |
| `AZURE_STORAGE_SAS_EXPIRY_MINUTES` | `prod.env` | `60` | No |
| `ALLOWED_ORIGINS` | `prod.env` | Restrict to known domains | No |
| `ENABLE_OPENAI` | `prod.env` | `true` for production | No |
| `OPENAI_API_KEY_SECRET_NAME` | `prod.env` | AKV secret name for OpenAI key | No |
| `DEBUG` | `prod.env` | `false` | No |
| `AZURE_CLIENT_ID` | deploy-time | UMSI client ID (set via `az containerapp update`) | No |
| `cosmos-db-connection-string` | AKV | Cosmos DB MongoDB connection URI | **Yes** |
| `jwt-secret-key` | AKV | HS256 signing key (64-char hex) | **Yes** |
| `openai-api-key` | AKV | OpenAI API key (`sk-...`) | **Yes** (only if `ENABLE_OPENAI=true`) |

> **Note:** The 3 "Manual AKV" secrets must be created with `az keyvault secret set` before first deployment. See [docs/AZURE_DEPLOYMENT.md](docs/AZURE_DEPLOYMENT.md) for commands.

---

## Azure Deployment

For end-to-end Azure setup commands (resource creation, RBAC, Container Apps deployment), see **[docs/AZURE_DEPLOYMENT.md](docs/AZURE_DEPLOYMENT.md)**.
