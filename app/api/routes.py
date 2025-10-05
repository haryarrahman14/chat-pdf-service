"""API routes for Chat PDF application"""
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from typing import Optional
import os
import uuid
import aiofiles
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    UploadResponse,
    ListDocumentsRequest,
    ListDocumentsResponse,
    DocumentCreate,
    DocumentResponse,
    DocumentStatus,
    MessageRole
)
from app.services.pdf_service import PDFService
from app.services.supabase_service import SupabaseService
from app.services.ingestion_service import IngestionService
from app.services.chat_service import ChatService
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Service instances
pdf_service = PDFService()
db_service = SupabaseService()
ingestion_service = IngestionService()
chat_service = ChatService()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = "00000000-0000-0000-0000-000000000000"  # TODO: Extract from JWT
):
    """
    Upload a PDF document

    Args:
        file: PDF file to upload
        user_id: User ID (from JWT in production)

    Returns:
        Upload response with document ID and status
    """
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=422, detail="Only PDF files are supported")

        # Read file content
        file_content = await file.read()

        # Check file size
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > settings.max_upload_size_mb:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum of {settings.max_upload_size_mb}MB"
            )

        # Compute SHA256 hash
        sha256 = pdf_service.compute_sha256(file_content)

        # Check for duplicate
        existing_doc = await db_service.get_document_by_hash(user_id, sha256)
        if existing_doc and existing_doc['status'] == DocumentStatus.READY.value:
            return UploadResponse(
                doc_id=existing_doc['id'],
                status=DocumentStatus.READY,
                filename=existing_doc['filename'],
                message="Document already exists and is ready"
            )

        # Save file locally
        os.makedirs(settings.upload_dir, exist_ok=True)
        file_id = str(uuid.uuid4())
        local_path = os.path.join(settings.upload_dir, f"{file_id}.pdf")

        async with aiofiles.open(local_path, 'wb') as f:
            await f.write(file_content)

        # Upload to Supabase Storage (optional, using local for now)
        storage_path = f"{user_id}/{file_id}.pdf"

        # Create document record
        doc_create = DocumentCreate(
            user_id=user_id,
            sha256=sha256,
            filename=file.filename,
            storage_path=storage_path
        )

        doc = await db_service.create_document(doc_create)

        # Queue background ingestion
        background_tasks.add_task(
            ingestion_service.ingest_document,
            doc['id'],
            local_path
        )

        return UploadResponse(
            doc_id=doc['id'],
            status=DocumentStatus.PENDING,
            filename=file.filename,
            message="File uploaded successfully. Ingestion started."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")


@router.get("/documents", response_model=ListDocumentsResponse)
async def list_documents(
    user_id: str = "00000000-0000-0000-0000-000000000000",  # TODO: Extract from JWT
    status: Optional[DocumentStatus] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    List documents for a user

    Args:
        user_id: User ID (from JWT in production)
        status: Filter by status (optional)
        limit: Maximum number of documents to return
        offset: Pagination offset

    Returns:
        List of documents with pagination info
    """
    try:
        documents, total = await db_service.list_documents(
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset
        )

        doc_responses = [
            DocumentResponse(
                id=doc['id'],
                user_id=doc['user_id'],
                sha256=doc['sha256'],
                filename=doc['filename'],
                status=DocumentStatus(doc['status']),
                page_count=doc.get('page_count'),
                created_at=doc['created_at'],
                updated_at=doc['updated_at']
            )
            for doc in documents
        ]

        return ListDocumentsResponse(
            documents=doc_responses,
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with selected documents using RAG

    Args:
        request: Chat request with question and document IDs

    Returns:
        Chat response with answer and citations
    """
    try:
        # Validate that all documents exist and are ready
        for doc_id in request.doc_ids:
            doc = await db_service.get_document(doc_id)
            if not doc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document {doc_id} not found"
                )
            if doc['status'] != DocumentStatus.READY.value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Document {doc_id} is not ready (status: {doc['status']})"
                )

        # Process chat
        answer, citations, token_usage = await chat_service.chat(
            question=request.question,
            doc_ids=request.doc_ids,
            model=request.model
        )

        # Create or get conversation
        conversation_id = request.conversation_id
        if not conversation_id:
            # Create new conversation
            conv = await db_service.create_conversation(
                user_id="00000000-0000-0000-0000-000000000000",  # TODO: Extract from JWT
                title=request.question[:100]  # Use question as title
            )
            conversation_id = conv['id']

        # Save user message
        user_msg = await db_service.create_message(
            conversation_id=conversation_id,
            role=MessageRole.USER.value,
            content=request.question,
            doc_ids=request.doc_ids
        )

        # Save assistant message
        assistant_msg = await db_service.create_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT.value,
            content=answer,
            citations=[citation.dict() for citation in citations],
            token_usage=token_usage
        )

        return ChatResponse(
            answer=answer,
            citations=citations,
            conversation_id=conversation_id,
            message_id=assistant_msg['id'],
            token_usage=token_usage
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "chat-pdf"}
