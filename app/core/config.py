"""
app/core/config.py
──────────────────
Central configuration module powered by Pydantic BaseSettings.

Environment strategy:
  • APP_ENV=local   → reads MONGODB_URL directly from the .env file.
                      Ideal for docker-compose local development.
  • APP_ENV=production → ignores MONGODB_URL and instead fetches the
                         Cosmos DB connection string securely from
                         Azure Key Vault using DefaultAzureCredential
                         (Managed Identity on Azure Container Apps).
                         Zero hardcoded credentials in production.

User-assigned Managed Identity (UMSI) requirement:
  When using a user-assigned managed identity (as opposed to a system-assigned
  one), AZURE_CLIENT_ID must be set to the client ID of the UMSI.
  DefaultAzureCredential cannot infer which identity to use when multiple are
  available — setting AZURE_CLIENT_ID tells the SDK exactly which one to use.

  Retrieve the client ID via:
    az identity show --name <umsi-name> --resource-group <rg> --query clientId -o tsv

  Set it as an environment variable on the Container App:
    az containerapp update --name <app> --resource-group <rg> \\
      --set-env-vars AZURE_CLIENT_ID=<client-id>
"""

from enum import Enum
from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
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
        env_file=".env",
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
        default="change-me-in-production-must-be-at-least-32-characters",
        description="HS256 signing key. Fetched from Key Vault in production.",
    )
    JWT_SECRET_NAME: str = Field(
        default="jwt-secret-key",
        description="Name of the Key Vault secret that holds the JWT signing key.",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

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
    # Required when using a user-assigned managed identity (UMSI).
    # DefaultAzureCredential reads this automatically — no extra code needed.
    # Retrieve with: az identity show --name <umsi> --query clientId -o tsv
    AZURE_CLIENT_ID: str = Field(
        default="",
        description=(
            "Client ID of the user-assigned managed identity. "
            "Required in production — DefaultAzureCredential uses this to "
            "select the correct UMSI when multiple identities are available."
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

    # ── CORS ──────────────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def load_secrets_from_akv(self) -> "Settings":
        """
        In production, fetch sensitive secrets from Azure Key Vault.
        This runs after all fields are initialized from environment variables.
        In local mode, env vars are used directly.
        """
        if self.APP_ENV == AppEnvironment.PRODUCTION:
        After load_secrets_from_akv() runs in production, this simply returns
        the value already fetched from Key Vault. In local mode, returns the
        environment variable directly.
        """
        return self.MONGODB_URLAME}' from Key Vault: {e}"
                ) from e

        return self

    ALLOWED_ORIGINS: List[str] = ["*"]

    # ─────────────────────────────────────────────────────────────────────────

    def get_mongodb_url(self) -> str:
        """
        Returns the MongoDB / Cosmos DB connection string.

        LOCAL:      Returns MONGODB_URL from environment — no Azure calls.
        PRODUCTION: Uses DefaultAzureCredential (Managed Identity) to fetch
                    the connection string from Azure Key Vault at startup.
                    This completely avoids hardcoded credentials.
        """
        if self.APP_ENV == AppEnvironment.LOCAL:
            return self.MONGODB_URL

        # ── Production: pull secret from Azure Key Vault ──────────────────
        # Import here to avoid loading Azure SDK in local dev environments.
        from azure.identity import DefaultAzureCredential          # noqa: PLC0415
        from azure.keyvault.secrets import SecretClient             # noqa: PLC0415

        if not self.AZURE_KEY_VAULT_URL:
            raise RuntimeError(
                "AZURE_KEY_VAULT_URL must be set when APP_ENV=production."
            )

        # Pass managed_identity_client_id explicitly so DefaultAzureCredential
        # always targets the correct UMSI (dharma-env-umsi).  Without this,
        # the SDK cannot resolve which user-assigned identity to use and the
        # token request fails with invalid_scope.
        credential = DefaultAzureCredential(
            managed_identity_client_id=self.AZURE_CLIENT_ID or None,
        )
        secret_client = SecretClient(
            vault_url=self.AZURE_KEY_VAULT_URL,
            credential=credential,
        )
        secret = secret_client.get_secret(self.COSMOS_DB_SECRET_NAME)
        return secret.value  # type: ignore[return-value]


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached singleton Settings instance.
    Using @lru_cache means environment variables are only parsed once
    at process startup, which is both fast and avoids repeated I/O.
    """
    return Settings()
