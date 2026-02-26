"""
app/admin/services/media_service.py
──────────────────────────────────
Media upload service for admin endpoints.
Handles uploading files to Azure Blob Storage and generating blob paths.
"""

import asyncio
from pathlib import Path
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient

from app.config.settings import AppEnvironment, get_settings


class MediaUploadService:
    """
    Uploads media files to Azure Blob Storage.

    In PRODUCTION mode (APP_ENV=production):
      • Uses DefaultAzureCredential to authenticate (Managed Identity)
      • Uploads to the configured container
      • Returns the relative blob path (e.g. "audio/audio_507f1f77bcf86cd799439011.mp3")

    In LOCAL mode (APP_ENV=local):
      • Returns a pretend path for testing (no Azure calls made)
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def _is_enabled(self) -> bool:
        """True only in production mode (APP_ENV=production)."""
        return self._settings.APP_ENV == AppEnvironment.PRODUCTION

    def generate_blob_path(
        self,
        field_name: str,  # e.g. "audio", "image", "gif"
        document_id: str,  # MongoDB ObjectId as string
        file_extension: str,  # e.g. ".mp3", ".jpg" (with dot)
    ) -> str:
        """
        Generate a blob storage path for a media file.

        Pattern: {field_name}/{field_name}_{document_id}{extension}
        Example: "audio/audio_507f1f77bcf86cd799439011.mp3"

        Args:
            field_name: Type of media field (audio, image, gif, icon)
            document_id: MongoDB document ID (ObjectId as string)
            file_extension: File extension with dot (.mp3, .jpg, etc.)

        Returns:
            Relative blob path (no container name, no SAS token)
        """
        return f"{field_name}/{field_name}_{document_id}{file_extension}"

    async def upload_file(
        self,
        file_bytes: bytes,
        field_name: str,
        document_id: str,
        file_extension: str,
    ) -> str:
        """
        Upload a file to Azure Blob Storage and return its relative path.

        Only works in PRODUCTION mode. In LOCAL mode, returns a pretend
        path for testing purposes.

        Args:
            file_bytes: The file content as bytes
            field_name: Type of media field (audio, image, gif, icon)
            document_id: MongoDB document ID (ObjectId as string)
            file_extension: File extension with dot (.mp3, .jpg, etc.)

        Returns:
            Relative blob path (will be signed by StorageService later)

        Raises:
            RuntimeError: If forced to upload in LOCAL mode (caller's mistake)
        """
        blob_path = self.generate_blob_path(field_name, document_id, file_extension)

        if not self._is_enabled:
            # For local testing, just return the path without uploading
            return blob_path

        # Offload the blocking Azure SDK call to thread pool
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            self._upload_to_azure_sync,
            file_bytes,
            blob_path,
        )

        return blob_path

    def _upload_to_azure_sync(self, file_bytes: bytes, blob_path: str) -> None:
        """
        Synchronous Azure Blob Storage upload.

        MUST only be called via run_in_executor to avoid blocking the
        async event loop.
        """
        credential = DefaultAzureCredential(
            managed_identity_client_id=self._settings.AZURE_CLIENT_ID or None,
        )

        container_url = (
            f"{self._settings.AZURE_STORAGE_ACCOUNT_URL.rstrip('/')}"
            f"/{self._settings.AZURE_STORAGE_CONTAINER}"
        )
        blob_client = BlobClient(
            account_url=self._settings.AZURE_STORAGE_ACCOUNT_URL,
            container_name=self._settings.AZURE_STORAGE_CONTAINER,
            blob_name=blob_path,
            credential=credential,
        )

        blob_client.upload_blob(
            data=file_bytes,
            overwrite=True,
        )


def get_media_upload_service() -> MediaUploadService:
    """FastAPI dependency: returns a MediaUploadService instance."""
    return MediaUploadService()
