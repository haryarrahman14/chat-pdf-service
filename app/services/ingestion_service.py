"""Document ingestion service"""
import os
from typing import Dict, Any
from app.services.pdf_service import PDFService
from app.services.embedding_service import EmbeddingService
from app.services.supabase_service import SupabaseService
from app.models.schemas import DocumentStatus
import logging

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting PDF documents"""

    def __init__(self):
        self.pdf_service = PDFService()
        self.embedding_service = EmbeddingService()
        self.db_service = SupabaseService()

    async def ingest_document(self, doc_id: str, file_path: str) -> None:
        """
        Ingest a PDF document: parse, chunk, embed, and store

        Args:
            doc_id: Document ID from database
            file_path: Path to the PDF file
        """
        try:
            # Update status to processing
            await self.db_service.update_document_status(
                doc_id,
                DocumentStatus.PROCESSING
            )

            logger.info(f"Starting ingestion for document {doc_id}")

            # 1. Extract text from PDF
            logger.info(f"Extracting text from {file_path}")
            full_text, page_count = self.pdf_service.extract_text_from_pdf(file_path)

            if not full_text.strip():
                raise ValueError("No text extracted from PDF")

            # 2. Chunk the text
            logger.info(f"Chunking text into chunks")
            chunks_data = self.pdf_service.chunk_text(
                full_text,
                chunk_size=800,
                overlap=150
            )

            logger.info(f"Created {len(chunks_data)} chunks")

            if not chunks_data:
                raise ValueError("No chunks created from document")

            # 3. Generate embeddings for all chunks
            logger.info(f"Generating embeddings for {len(chunks_data)} chunks")
            chunk_texts = [chunk['content'] for chunk in chunks_data]
            embeddings = await self.embedding_service.generate_embeddings_batch(
                chunk_texts,
                batch_size=100
            )

            # 4. Prepare chunks for database insertion
            db_chunks = []
            for chunk_data, embedding in zip(chunks_data, embeddings):
                db_chunks.append({
                    "doc_id": doc_id,
                    "content": chunk_data['content'],
                    "embedding": embedding,
                    "page_start": chunk_data.get('page_start'),
                    "page_end": chunk_data.get('page_end'),
                    "section": chunk_data.get('section'),
                    "token_count": chunk_data.get('token_count', 0)
                })

            # 5. Insert chunks into database
            logger.info(f"Inserting {len(db_chunks)} chunks into database")
            await self.db_service.insert_chunks(db_chunks)

            # 6. Update document status to ready
            await self.db_service.update_document_status(
                doc_id,
                DocumentStatus.READY,
                page_count=page_count
            )

            logger.info(f"Successfully ingested document {doc_id}")

        except Exception as e:
            logger.error(f"Error ingesting document {doc_id}: {str(e)}", exc_info=True)

            # Update status to failed
            await self.db_service.update_document_status(
                doc_id,
                DocumentStatus.FAILED
            )

            raise

    async def reingest_document(self, doc_id: str, file_path: str) -> None:
        """
        Re-ingest a document (delete old chunks and ingest new)

        Args:
            doc_id: Document ID
            file_path: Path to the PDF file
        """
        # Delete old chunks
        await self.db_service.delete_document_chunks(doc_id)

        # Ingest the document
        await self.ingest_document(doc_id, file_path)
