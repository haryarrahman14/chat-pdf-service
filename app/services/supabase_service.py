"""Supabase database service"""
from typing import List, Optional, Dict, Any
from supabase import create_client, Client
from app.core.config import settings
from app.models.schemas import DocumentCreate, DocumentStatus
import json


class SupabaseService:
    """Service for interacting with Supabase database"""

    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_key  # Use service key to bypass RLS for workers
        )

    # Document operations
    async def create_document(self, doc: DocumentCreate) -> Dict[str, Any]:
        """Create a new document record"""
        data = {
            "user_id": doc.user_id,
            "sha256": doc.sha256,
            "filename": doc.filename,
            "storage_path": doc.storage_path,
            "status": DocumentStatus.PENDING.value,
            "page_count": doc.page_count
        }

        response = self.client.table("documents").insert(data).execute()
        return response.data[0] if response.data else None

    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        response = self.client.table("documents").select("*").eq("id", doc_id).execute()
        return response.data[0] if response.data else None

    async def update_document_status(
        self,
        doc_id: str,
        status: DocumentStatus,
        page_count: Optional[int] = None
    ) -> None:
        """Update document status"""
        data = {"status": status.value}
        if page_count is not None:
            data["page_count"] = page_count

        self.client.table("documents").update(data).eq("id", doc_id).execute()

    async def list_documents(
        self,
        user_id: str,
        status: Optional[DocumentStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Dict[str, Any]], int]:
        """List documents for a user"""
        query = self.client.table("documents").select("*", count="exact")
        query = query.eq("user_id", user_id)

        if status:
            query = query.eq("status", status.value)

        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + limit - 1)

        response = query.execute()

        return response.data, response.count or 0

    async def get_document_by_hash(
        self,
        user_id: str,
        sha256: str
    ) -> Optional[Dict[str, Any]]:
        """Check if document with same hash exists for user"""
        response = (
            self.client.table("documents")
            .select("*")
            .eq("user_id", user_id)
            .eq("sha256", sha256)
            .order("version", desc=True)
            .limit(1)
            .execute()
        )

        return response.data[0] if response.data else None

    # Chunk operations
    async def insert_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """Bulk insert chunks"""
        # Supabase client handles batching automatically
        self.client.table("chunks").insert(chunks).execute()

    async def search_chunks(
        self,
        query_embedding: List[float],
        doc_ids: List[str],
        match_threshold: float = 0.7,
        match_count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using vector similarity

        Uses the match_chunks function defined in schema.sql
        """
        response = self.client.rpc(
            "match_chunks",
            {
                "query_embedding": query_embedding,
                "filter_doc_ids": doc_ids,
                "match_threshold": match_threshold,
                "match_count": match_count
            }
        ).execute()

        return response.data if response.data else []

    async def delete_document_chunks(self, doc_id: str) -> None:
        """Delete all chunks for a document"""
        self.client.table("chunks").delete().eq("doc_id", doc_id).execute()

    # Conversation operations
    async def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new conversation"""
        data = {
            "user_id": user_id,
            "title": title or "New Conversation"
        }

        response = self.client.table("conversations").insert(data).execute()
        return response.data[0] if response.data else None

    async def create_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        doc_ids: Optional[List[str]] = None,
        citations: Optional[List[dict]] = None,
        token_usage: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Create a new message in a conversation"""
        data = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "doc_ids": doc_ids,
            "citations": json.dumps(citations) if citations else None,
            "token_usage": json.dumps(token_usage) if token_usage else None
        }

        response = self.client.table("messages").insert(data).execute()
        return response.data[0] if response.data else None

    # Storage operations
    async def upload_file(
        self,
        bucket_name: str,
        file_path: str,
        file_content: bytes,
        content_type: str = "application/pdf"
    ) -> str:
        """Upload file to Supabase Storage"""
        response = self.client.storage.from_(bucket_name).upload(
            file_path,
            file_content,
            {
                "content-type": content_type,
                "upsert": "false"
            }
        )

        return file_path

    async def get_signed_url(
        self,
        bucket_name: str,
        file_path: str,
        expires_in: int = 3600
    ) -> str:
        """Get signed URL for file access"""
        response = self.client.storage.from_(bucket_name).create_signed_url(
            file_path,
            expires_in
        )

        return response.get("signedURL", "")

    async def delete_file(self, bucket_name: str, file_path: str) -> None:
        """Delete file from storage"""
        self.client.storage.from_(bucket_name).remove([file_path])
