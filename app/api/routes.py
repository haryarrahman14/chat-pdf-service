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
    MessageRole,
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse
)
from app.services.pdf_service import PDFService
from app.services.supabase_service import SupabaseService
from app.services.ingestion_service import IngestionService
from app.services.chat_service import ChatService
from app.services.auth_service import AuthService
from app.services.storage_service import StorageService
from app.core.config import settings
from app.core.dependencies import get_current_user_id
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Service instances
pdf_service = PDFService()
db_service = SupabaseService()
ingestion_service = IngestionService()
chat_service = ChatService()
auth_service = AuthService()
storage_service = StorageService()


# Authentication endpoints
@router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    """
    Register a new user using Supabase Auth

    Args:
        user_data: User registration data (email, password, optional full_name)

    Returns:
        JWT access token and user information
    """
    try:
        # Register user with Supabase Auth
        result = await auth_service.register_user(
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name
        )

        user = result["user"]
        session = result["session"]

        return TokenResponse(
            access_token=session.access_token,
            user_id=user.id,
            email=user.email
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error registering user: {str(e)}")


@router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """
    Login with email and password using Supabase Auth

    Args:
        credentials: User login credentials (email, password)

    Returns:
        JWT access token and user information
    """
    try:
        # Login user with Supabase Auth
        result = await auth_service.login_user(
            email=credentials.email,
            password=credentials.password
        )

        user = result["user"]
        session = result["session"]

        return TokenResponse(
            access_token=session.access_token,
            user_id=user.id,
            email=user.email
        )

    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    except Exception as e:
        logger.error(f"Error logging in: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error logging in: {str(e)}")


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id)
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

        # Upload file to storage (Supabase Storage or local)
        file_id = str(uuid.uuid4())
        storage_path, local_temp_path = await storage_service.upload_pdf(
            file_content=file_content,
            user_id=user_id,
            file_id=file_id,
            filename=file.filename
        )

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
            local_temp_path,
            cleanup_after=settings.use_supabase_storage  # Cleanup temp file if using Supabase Storage
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
    user_id: str = Depends(get_current_user_id),
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
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)):
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
                user_id=user_id,
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
