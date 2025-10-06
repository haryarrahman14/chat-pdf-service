"""Storage service for managing file uploads and downloads"""

from typing import Optional
import tempfile
import os
from app.services.supabase_service import SupabaseService
from app.core.config import settings
import logging
import httpx

logger = logging.getLogger(__name__)


class StorageService:
    """Service for file storage operations using Supabase Storage"""

    def __init__(self):
        self.db_service = SupabaseService()
        self.bucket_name = settings.storage_bucket_name
        self.use_supabase_storage = settings.use_supabase_storage

    async def upload_pdf(
        self, file_content: bytes, user_id: str, file_id: str, filename: str
    ) -> tuple[str, str]:
        """
        Upload PDF file to storage

        Args:
            file_content: PDF file content as bytes
            user_id: User ID for organizing files
            file_id: Unique file identifier
            filename: Original filename

        Returns:
            Tuple of (storage_path, local_temp_path)
            - storage_path: Path in Supabase Storage or local path
            - local_temp_path: Temporary local path for processing
        """
        storage_path = f"{user_id}/{file_id}.pdf"

        if self.use_supabase_storage:
            # Upload to Supabase Storage
            try:
                await self.db_service.upload_file(
                    bucket_name=self.bucket_name,
                    file_path=storage_path,
                    file_content=file_content,
                    content_type="application/pdf",
                )
                logger.info(f"Uploaded file to Supabase Storage: {storage_path}")
            except Exception as e:
                logger.error(f"Error uploading to Supabase Storage: {str(e)}")
                raise

            # Also save to temp file for immediate processing
            temp_dir = tempfile.gettempdir()
            local_temp_path = os.path.join(temp_dir, f"{file_id}.pdf")
            with open(local_temp_path, "wb") as f:
                f.write(file_content)

        else:
            # Save to local storage
            os.makedirs(settings.upload_dir, exist_ok=True)
            local_temp_path = os.path.join(settings.upload_dir, f"{file_id}.pdf")
            with open(local_temp_path, "wb") as f:
                f.write(file_content)
            logger.info(f"Saved file locally: {local_temp_path}")

        return storage_path, local_temp_path

    async def download_pdf(self, storage_path: str) -> str:
        """
        Download PDF from storage to a temporary local file

        Args:
            storage_path: Path in Supabase Storage or local path

        Returns:
            Path to the temporary local file
        """
        if self.use_supabase_storage:
            # Download from Supabase Storage via signed URL
            try:
                signed_url = await self.db_service.get_signed_url(
                    bucket_name=self.bucket_name,
                    file_path=storage_path,
                    expires_in=3600,  # 1 hour
                )

                # Download file content
                async with httpx.AsyncClient() as client:
                    response = await client.get(signed_url)
                    response.raise_for_status()
                    file_content = response.content

                # Save to temp file
                file_id = storage_path.split("/")[-1].replace(".pdf", "")
                temp_dir = tempfile.gettempdir()
                local_path = os.path.join(temp_dir, f"{file_id}.pdf")

                with open(local_path, "wb") as f:
                    f.write(file_content)

                logger.info(f"Downloaded file from Supabase Storage to: {local_path}")
                return local_path

            except Exception as e:
                logger.error(f"Error downloading from Supabase Storage: {str(e)}")
                raise

        else:
            # Local storage - construct path
            file_id = storage_path.split("/")[-1].replace(".pdf", "")
            local_path = os.path.join(settings.upload_dir, f"{file_id}.pdf")

            if not os.path.exists(local_path):
                raise FileNotFoundError(f"File not found: {local_path}")

            return local_path

    async def delete_pdf(self, storage_path: str) -> None:
        """
        Delete PDF from storage

        Args:
            storage_path: Path in Supabase Storage or local path
        """
        if self.use_supabase_storage:
            try:
                await self.db_service.delete_file(
                    bucket_name=self.bucket_name, file_path=storage_path
                )
                logger.info(f"Deleted file from Supabase Storage: {storage_path}")
            except Exception as e:
                logger.error(f"Error deleting from Supabase Storage: {str(e)}")
                raise
        else:
            # Local storage
            file_id = storage_path.split("/")[-1].replace(".pdf", "")
            local_path = os.path.join(settings.upload_dir, f"{file_id}.pdf")

            if os.path.exists(local_path):
                os.remove(local_path)
                logger.info(f"Deleted local file: {local_path}")

    async def get_file_url(
        self, storage_path: str, expires_in: int = 3600
    ) -> Optional[str]:
        """
        Get a signed URL for file access

        Args:
            storage_path: Path in Supabase Storage or local path
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Signed URL or None if using local storage
        """
        if self.use_supabase_storage:
            try:
                signed_url = await self.db_service.get_signed_url(
                    bucket_name=self.bucket_name,
                    file_path=storage_path,
                    expires_in=expires_in,
                )
                return signed_url
            except Exception as e:
                logger.error(f"Error getting signed URL: {str(e)}")
                raise
        else:
            # Local storage doesn't support signed URLs
            return None

    async def cleanup_temp_file(self, local_path: str) -> None:
        """
        Clean up temporary local file

        Args:
            local_path: Path to temporary file
        """
        try:
            if os.path.exists(local_path) and tempfile.gettempdir() in local_path:
                os.remove(local_path)
                logger.debug(f"Cleaned up temp file: {local_path}")
        except Exception as e:
            logger.warning(f"Error cleaning up temp file {local_path}: {str(e)}")
