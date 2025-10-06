"""Main FastAPI application"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import settings
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Chat PDF API",
    description="RAG-based chat system for PDF documents with OpenAI",
    version="1.0.0",
    debug=settings.debug,
)

# Add CORS middleware
# Production: configure allowed origins from environment
allowed_origins = settings.cors_origins.split(",") if settings.cors_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api", tags=["chat-pdf"])


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("Starting Chat PDF API...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("Shutting down Chat PDF API...")


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Chat PDF API", "version": "1.0.0", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
