"""Pydantic schemas for API requests and responses"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class DocumentStatus(str, Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class MessageRole(str, Enum):
    """Chat message role"""
    USER = "user"
    ASSISTANT = "assistant"


# Document Schemas
class DocumentBase(BaseModel):
    """Base document schema"""
    filename: str


class DocumentCreate(DocumentBase):
    """Schema for creating a document"""
    user_id: str
    sha256: str
    storage_path: str
    page_count: Optional[int] = None


class DocumentResponse(DocumentBase):
    """Schema for document response"""
    id: str
    user_id: str
    sha256: str
    status: DocumentStatus
    page_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Chunk Schemas
class ChunkCreate(BaseModel):
    """Schema for creating a chunk"""
    doc_id: str
    content: str
    embedding: List[float]
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section: Optional[str] = None
    token_count: int


# Chat Schemas
class Citation(BaseModel):
    """Citation schema"""
    doc_id: str
    filename: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    snippet: str = Field(..., max_length=200)


class ChatRequest(BaseModel):
    """Schema for chat request"""
    question: str = Field(..., min_length=1, max_length=2000)
    doc_ids: List[str] = Field(..., min_items=1)
    conversation_id: Optional[str] = None
    model: Optional[str] = None  # gpt-4o or gpt-4o-mini


class ChatResponse(BaseModel):
    """Schema for chat response"""
    answer: str
    citations: List[Citation]
    conversation_id: str
    message_id: str
    token_usage: Optional[dict] = None


# Upload Schemas
class UploadResponse(BaseModel):
    """Schema for upload response"""
    doc_id: str
    status: DocumentStatus
    filename: str
    message: str = "File uploaded successfully"


# List Documents Schemas
class ListDocumentsRequest(BaseModel):
    """Schema for listing documents"""
    user_id: str
    status: Optional[DocumentStatus] = None
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)


class ListDocumentsResponse(BaseModel):
    """Schema for list documents response"""
    documents: List[DocumentResponse]
    total: int
    limit: int
    offset: int


# Conversation Schemas
class ConversationCreate(BaseModel):
    """Schema for creating a conversation"""
    user_id: str
    title: Optional[str] = None


class MessageCreate(BaseModel):
    """Schema for creating a message"""
    conversation_id: str
    role: MessageRole
    content: str
    doc_ids: Optional[List[str]] = None
    citations: Optional[List[dict]] = None
    token_usage: Optional[dict] = None
