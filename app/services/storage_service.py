"""
app/services/storage_service.py
─────────────────────────────────
Azure Blob Storage SAS URL generation service.

Responsibilities:
  • Generates short-lived User Delegation SAS URLs for private blobs so the
    React Native client can stream media assets without needing public access.
  • Caches the UserDelegationKey for _KEY_CACHE_TTL_HOURS (2 h) to avoid one
    blocking Azure network call per API request.
  • Exposes sign_media_fields(data: dict) -> dict which replaces the four
    known media path fields with full signed URLs.

URL field convention:
  MongoDB stores relative blob PATHS (e.g. "audio/verse.mp3"), NOT full URLs.
  sign_media_fields constructs the full SAS URL:
    {AZURE_STORAGE_ACCOUNT_URL}/{AZURE_STORAGE_CONTAINER}/{blob_path}?{sas_token}

LOCAL / PRODUCTION behaviour:
  • LOCAL  (AZURE_STORAGE_ACCOUNT_URL is empty): all methods are no-ops;
    original path values are returned unchanged. No Azure SDK calls are made.
  • PRODUCTION: UserDelegationKey is lazily fetched on the first request
    and refreshed when it approaches expiry.

Threading / async safety:
  • BlobServiceClient.get_user_delegation_key() is a SYNCHRONOUS blocking
    network call. Calling it directly inside an async route would block the
    entire uvicorn event loop.
  • _fetch_delegation_key_sync() is always called via
    asyncio.get_running_loop().run_in_executor(None, ...) so the event loop
    stays free during the Azure round-trip.
  • generate_blob_sas() is pure HMAC computation — zero I/O, always safe
    to call synchronously inside an async function.
  • A threading.Lock guards the cache so that under concurrent requests only
    one thread calls Azure; the rest wait then reuse the fresh key.
"""

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    UserDelegationKey,
    generate_blob_sas,
)

from app.core.config import get_settings

# UserDelegationKey cache TTL. Azure enforces a maximum of 7 days;
# 2 hours is conservative and always greater than any SAS expiry.
_KEY_CACHE_TTL_HOURS: int = 2

# The four media path fields that may appear in ingredient dicts.
_MEDIA_FIELDS: tuple[str, ...] = ("audio_url", "gif_url", "image_url", "icon_url")


class StorageService:
    """
    Generates Azure Blob Storage User Delegation SAS URLs.

    Instantiate once per process (use get_storage_service() below).
    The internal delegation key cache is per-instance — sharing a single
    instance across all requests is critical for cache effectiveness.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._account_name: str = self._parse_account_name()
        self._container: str = self._settings.AZURE_STORAGE_CONTAINER

        # Delegation key cache state.
        self._delegation_key: Optional[UserDelegationKey] = None
        self._key_expiry: Optional[datetime] = None
        self._lock = threading.Lock()

    # ── Private helpers ────────────────────────────────────────────────────────

    def _parse_account_name(self) -> str:
        """
        Extract the storage account name from AZURE_STORAGE_ACCOUNT_URL.

        "https://dharmastorage.blob.core.windows.net"  →  "dharmastorage"
        ""  →  ""  (triggers no-op mode)
        """
        url = self._settings.AZURE_STORAGE_ACCOUNT_URL
        if not url:
            return ""
        hostname = urlparse(url).hostname or ""
        return hostname.split(".")[0]

    @property
    def _is_enabled(self) -> bool:
        """True only when Azure Blob Storage is configured (production)."""
        return bool(self._settings.AZURE_STORAGE_ACCOUNT_URL)

    def _key_needs_refresh(self) -> bool:
        """
        Return True if the cached delegation key is absent or about to expire.
        Uses a 5-minute safety margin to proactively refresh before actual expiry.
        """
        if self._delegation_key is None or self._key_expiry is None:
            return True
        return datetime.now(timezone.utc) >= (self._key_expiry - timedelta(minutes=5))

    def _fetch_delegation_key_sync(self) -> UserDelegationKey:
        """
        Blocking call to Azure to obtain a UserDelegationKey.

        MUST be called only via run_in_executor, never directly from an
        async function, to avoid blocking the event loop.

        A threading.Lock ensures that under concurrent requests only one
        thread calls Azure; all others wait, then reuse the cached key.

        The key validity window starts 1 minute in the past (clock skew
        tolerance) and expires _KEY_CACHE_TTL_HOURS from now.
        """
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415

        credential = DefaultAzureCredential(
            managed_identity_client_id=self._settings.AZURE_CLIENT_ID or None,
        )
        client = BlobServiceClient(
            account_url=self._settings.AZURE_STORAGE_ACCOUNT_URL,
            credential=credential,
        )

        now = datetime.now(timezone.utc)
        key_start = now - timedelta(minutes=1)
        key_expiry = now + timedelta(hours=_KEY_CACHE_TTL_HOURS)

        delegation_key = client.get_user_delegation_key(
            key_start_time=key_start,
            key_expiry_time=key_expiry,
        )

        with self._lock:
            self._delegation_key = delegation_key
            self._key_expiry = key_expiry

        return delegation_key

    async def _ensure_delegation_key(self) -> UserDelegationKey:
        """
        Async-safe method that returns a valid UserDelegationKey.

        Fast path (cached key still valid): returns immediately with no I/O.
        Slow path (key absent or stale): offloads the blocking SDK call to
        the default ThreadPoolExecutor via run_in_executor so the event loop
        remains free during the Azure round-trip.
        """
        if not self._key_needs_refresh():
            return self._delegation_key  # type: ignore[return-value]

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_delegation_key_sync)

    def _build_sas_url(self, blob_path: str, delegation_key: UserDelegationKey) -> str:
        """
        Generate a full signed URL for a blob path.

        generate_blob_sas() performs only HMAC-SHA256 computation over the
        delegation key material — zero network calls, always safe to call
        synchronously inside an async context.

        The SAS grants read-only permission, which is sufficient for the
        React Native client to stream/download media assets.
        """
        expiry = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.AZURE_STORAGE_SAS_EXPIRY_MINUTES
        )

        sas_token = generate_blob_sas(
            account_name=self._account_name,
            container_name=self._container,
            blob_name=blob_path,
            user_delegation_key=delegation_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry,
        )

        base_url = (
            f"{self._settings.AZURE_STORAGE_ACCOUNT_URL.rstrip('/')}"
            f"/{self._container}/{blob_path}"
        )
        return f"{base_url}?{sas_token}"

    # ── Public API ─────────────────────────────────────────────────────────────

    async def sign_media_fields(self, data: dict) -> dict:
        """
        Return a shallow copy of data with all media path fields replaced by
        full signed Azure Blob URLs.

        Fields processed: audio_url, gif_url, image_url, icon_url.

        Skipped silently when:
          • Storage is not configured (LOCAL mode, AZURE_STORAGE_ACCOUNT_URL empty)
          • The field is absent from data
          • The field value is "" (default for un-uploaded assets) or non-string

        The UserDelegationKey is fetched/cached once per call, not once per
        field, to minimise overhead when multiple fields are present.
        """
        if not self._is_enabled:
            return data

        signed = dict(data)
        delegation_key: Optional[UserDelegationKey] = None

        for field in _MEDIA_FIELDS:
            blob_path = signed.get(field)
            if not blob_path or not isinstance(blob_path, str):
                continue

            # Lazy-fetch once per sign_media_fields call, reuse for all fields.
            if delegation_key is None:
                delegation_key = await self._ensure_delegation_key()

            signed[field] = self._build_sas_url(blob_path, delegation_key)

        return signed


# ── Module-level singleton ─────────────────────────────────────────────────────

_storage_service: Optional[StorageService] = None
_service_lock = threading.Lock()


def get_storage_service() -> StorageService:
    """
    Returns the process-wide StorageService singleton.

    Thread-safe lazy initialisation via double-checked locking. Using a
    module-level singleton (rather than FastAPI Depends) is intentional:
    StorageService holds the delegation key cache — a new instance per
    request would defeat the caching entirely.
    """
    global _storage_service
    if _storage_service is None:
        with _service_lock:
            if _storage_service is None:
                _storage_service = StorageService()
    return _storage_service
