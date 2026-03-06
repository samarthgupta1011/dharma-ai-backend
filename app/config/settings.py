"""
config/settings.py
──────────────────
Central configuration module with strict validation.

Configuration Strategy:
  • LOCAL (APP_ENV=local):
      - Reads all values from .env file
      - No Azure SDK calls
      - Weak defaults allow quick testing
      - MONGODB_URL points to local docker-compose MongoDB

  • PRODUCTION (APP_ENV=production):
      - Reads from Azure Container Apps environment variables
      - Fetches secrets from Azure Key Vault via Managed Identity
      - STRICT validation—fails at startup if critical config is missing
      - Zero hardcoded credentials

Validation:
  Two validators run in sequence:
    1. load_secrets_from_akv() — Fetches secrets from AKV in production
    2. validate_required_vars() — Checks all required fields are present
  
  Startup fails immediately with helpful error messages if:
    - Critical env vars are missing
    - UMSI lacks permissions to access secrets
    - Secrets don't exist in AKV
    - JWT key is too short (< 32 chars)

User-assigned Managed Identity (UMSI):
  In production, AZURE_CLIENT_ID must be set to the UMSI's client ID so that
  DefaultAzureCredential can select the correct identity. Retrieve via:
    az identity show --name dharma-env-umsi --query clientId -o tsv
"""

from enum import Enum
from functools import lru_cache
from typing import List, Union

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(str, Enum):
    """Distinguishes local development from an Azure-hosted deployment."""
    LOCAL = "local"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    All configuration is loaded from environment variables (or a .env file).
    Sensitive production values are never stored here — they are fetched
    at runtime from Azure Key Vault via Managed Identity.
    """

    model_config = SettingsConfigDict(
        env_file="app/config/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_ENV: AppEnvironment = AppEnvironment.LOCAL
    APP_NAME: str = "Dharma AI Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(
        default="",
        description=(
            "HS256 signing key (32+ chars). In LOCAL mode, read from .env. "
            "In PRODUCTION, fetched from Azure Key Vault—must not be set in env."
        ),
    )
    JWT_SECRET_NAME: str = Field(
        default="jwt-secret-key",
        description="Name of the Key Vault secret containing JWT signing key (prod only).",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── OpenAI API ────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(
        default="",
        description=(
            "API key for OpenAI. In LOCAL mode, read from .env. "
            "In PRODUCTION, fetched from Azure Key Vault—must not be set in env."
        ),
    )
    OPENAI_API_KEY_SECRET_NAME: str = Field(
        default="openai-api-key",
        description="Name of the Key Vault secret containing OpenAI API key (prod only).",
    )
    ENABLE_OPENAI: bool = Field(
        default=False,
        description=(
            "Enable OpenAI API calls for Gita verse selection and reflections. "
            "Set to False in LOCAL dev to save tokens. When disabled, mock data is returned."
        ),
    )

    # ── Local MongoDB (only used when APP_ENV=local) ──────────────────────────
    # In local development we connect to MongoDB 6.0 running in docker-compose.
    # MongoDB 6.0 implements the same wire protocol as Azure Cosmos DB API for
    # MongoDB v6.0, so local and production behaviour are identical for all
    # features this codebase uses ($sample, unique/compound indexes, CRUD).
    #
    # When running inside docker-compose, this is overridden by the MONGODB_URL
    # env var set in docker-compose.yml (mongodb://mongo:27017 — Docker DNS).
    # When running bare-metal the default below (localhost:27017) is used.
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "dharma_db"

    # ── Azure Managed Identity ────────────────────────────────────────────────
    # Required when using a user-assigned managed identity (UMSI) in production.
    # DefaultAzureCredential reads this automatically.
    # Retrieve with: az identity show --name <umsi-name> --query clientId -o tsv
    AZURE_CLIENT_ID: str = Field(
        default="",
        description=(
            "Client ID of the user-assigned managed identity. "
            "REQUIRED in production—DefaultAzureCredential uses this to select the correct UMSI."
        ),
    )

    # ── Azure Key Vault (used in production) ──────────────────────────────────
    AZURE_KEY_VAULT_URL: str = Field(
        default="",
        description="e.g. https://dharma-kv.vault.azure.net/",
    )
    COSMOS_DB_SECRET_NAME: str = Field(
        default="cosmos-db-connection-string",
        description="Name of the Key Vault secret that holds the Cosmos DB URI.",
    )

    # ── Azure Blob Storage ────────────────────────────────────────────────────
    AZURE_STORAGE_ACCOUNT_URL: str = Field(
        default="",
        description="e.g. https://dharmastorage.blob.core.windows.net",
    )
    AZURE_STORAGE_CONTAINER: str = "dharma-media"
    AZURE_STORAGE_SAS_EXPIRY_MINUTES: int = Field(
        default=60,
        description="Lifetime in minutes for generated Blob SAS URLs.",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["*"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Accept '*', a JSON list, or a comma-separated string."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v == "*":
                return ["*"]
            # Try JSON first (e.g. '["https://example.com"]')
            if v.startswith("["):
                import json
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed]
                except json.JSONDecodeError:
                    pass
            # Fallback: comma-separated
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return ["*"]

    # ─────────────────────────────────────────────────────────────────────────

    @model_validator(mode="after")
    def load_secrets_from_akv(self) -> "Settings":
        """
        In production, fetch sensitive secrets from Azure Key Vault.
        This runs after all fields are initialized from environment variables.
        In local mode, env vars are used directly.
        """
        if self.APP_ENV == AppEnvironment.PRODUCTION:
            from azure.identity import DefaultAzureCredential          # noqa: PLC0415
            from azure.keyvault.secrets import SecretClient             # noqa: PLC0415

            if not self.AZURE_KEY_VAULT_URL:
                raise RuntimeError(
                    "PRODUCTION: AZURE_KEY_VAULT_URL must be set. "
                    "Configure in prod.env or Container App env vars."
                )

            credential = DefaultAzureCredential(
                managed_identity_client_id=self.AZURE_CLIENT_ID or None,
            )
            secret_client = SecretClient(
                vault_url=self.AZURE_KEY_VAULT_URL,
                credential=credential,
            )

            # Fetch Cosmos DB connection string from AKV
            try:
                cosmos_secret = secret_client.get_secret(self.COSMOS_DB_SECRET_NAME)
                self.MONGODB_URL = cosmos_secret.value  # type: ignore[assignment]
            except Exception as e:
                raise RuntimeError(
                    f"PRODUCTION: Failed to fetch Cosmos DB secret '{self.COSMOS_DB_SECRET_NAME}' from Key Vault. "
                    f"Ensure the secret exists and UMSI has 'Key Vault Secrets User' role. Error: {e}"
                ) from e

            # Fetch JWT secret from AKV
            try:
                jwt_secret = secret_client.get_secret(self.JWT_SECRET_NAME)
                self.JWT_SECRET_KEY = jwt_secret.value  # type: ignore[assignment]
            except Exception as e:
                raise RuntimeError(
                    f"PRODUCTION: Failed to fetch JWT secret '{self.JWT_SECRET_NAME}' from Key Vault. "
                    f"Ensure the secret exists and UMSI has 'Key Vault Secrets User' role. Error: {e}"
                ) from e

            # Fetch OpenAI API key from AKV
            try:
                openai_secret = secret_client.get_secret(self.OPENAI_API_KEY_SECRET_NAME)
                self.OPENAI_API_KEY = openai_secret.value  # type: ignore[assignment]
            except Exception as e:
                raise RuntimeError(
                    f"PRODUCTION: Failed to fetch OpenAI API key '{self.OPENAI_API_KEY_SECRET_NAME}' from Key Vault. "
                    f"Ensure the secret exists and UMSI has 'Key Vault Secrets User' role. Error: {e}"
                ) from e

        return self

    @model_validator(mode="after")
    def validate_required_vars(self) -> "Settings":
        """
        Validate that all required configuration is present.
        Runs AFTER load_secrets_from_akv, so secrets are already loaded.
        Provides clear error messages for missing or invalid configuration.
        """
        # Always required
        if not self.DATABASE_NAME:
            raise ValueError("DATABASE_NAME is required (should be 'dharma_db')")

        if not self.JWT_ALGORITHM:
            raise ValueError("JWT_ALGORITHM is required (should be 'HS256')")

        # LOCAL mode requirements
        if self.APP_ENV == AppEnvironment.LOCAL:
            if not self.MONGODB_URL:
                raise ValueError(
                    "LOCAL mode: MONGODB_URL is required. "
                    "Set in .env (default: mongodb://localhost:27017)"
                )

            if not self.JWT_SECRET_KEY:
                raise ValueError(
                    "LOCAL mode: JWT_SECRET_KEY is required in .env. "
                    "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )

            if self.ENABLE_OPENAI and not self.OPENAI_API_KEY:
                raise ValueError(
                    "LOCAL mode: ENABLE_OPENAI=true requires OPENAI_API_KEY in .env. "
                    "Get your key from https://platform.openai.com/api-keys"
                )

        # PRODUCTION mode requirements
        elif self.APP_ENV == AppEnvironment.PRODUCTION:
            if not self.AZURE_KEY_VAULT_URL:
                raise ValueError(
                    "PRODUCTION: AZURE_KEY_VAULT_URL is required. "
                    "Set in prod.env (e.g., https://dharma-kv.vault.azure.net/)"
                )

            if not self.AZURE_CLIENT_ID:
                raise ValueError(
                    "PRODUCTION: AZURE_CLIENT_ID (UMSI client ID) is required. "
                    "Set via: --set-env-vars AZURE_CLIENT_ID=$(az identity show --name dharma-env-umsi --query clientId -o tsv)"
                )

            if not self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "PRODUCTION: JWT_SECRET_KEY not properly loaded from Key Vault or is invalid. "
                    "Ensure 'jwt-secret-key' secret exists in AKV with 32+ characters."
                )

            if not self.MONGODB_URL:
                raise ValueError(
                    "PRODUCTION: Cosmos DB connection string not loaded from Key Vault. "
                    "Ensure 'cosmos-db-connection-string' secret exists in AKV."
                )

            if self.ENABLE_OPENAI and not self.OPENAI_API_KEY:
                raise ValueError(
                    "PRODUCTION: ENABLE_OPENAI=true requires OpenAI API key loaded from Key Vault. "
                    "Ensure 'openai-api-key' secret exists in AKV."
                )

        return self

    def get_mongodb_url(self) -> str:
        """Return the MongoDB/Cosmos DB connection URL (populated by validators)."""
        return self.MONGODB_URL


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached singleton Settings instance.
    Using @lru_cache means environment variables are only parsed once
    at process startup, which is both fast and avoids repeated I/O.
    """
    return Settings()
