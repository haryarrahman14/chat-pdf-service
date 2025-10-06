# Chat PDF - RAG-based PDF Question Answering System

A production-ready system for uploading PDFs, generating embeddings, and chatting with documents using retrieval-augmented generation (RAG) with OpenAI and Supabase.

## Features

- 📄 **PDF Upload & Processing**: Upload PDFs with automatic text extraction and chunking
- 🔍 **Vector Search**: Fast semantic search using Supabase pgvector
- 💬 **RAG Chat**: Chat with your documents with cited responses
- 🔒 **Multi-tenant**: Row-level security with Supabase
- 🛠️ **MCP Integration**: Model Context Protocol server for AI agent integration
- ⚡ **Async Processing**: Background ingestion with FastAPI

## Architecture

```
Client/UI
    ↓
FastAPI Server (app/main.py)
    ↓
├── Upload → Supabase Storage + Background Worker
├── Ingestion → PDF Parse → Chunk → OpenAI Embeddings → pgvector
└── Chat → Query Embedding → Vector Search → OpenAI Chat → Citations
    ↓
MCP Server (mcp_server/server.py)
    ↓
Tools: list_docs, add_doc, chat_with_docs
```

## Prerequisites

- Python 3.11+
- Supabase account (free tier works)
- OpenAI API key

## Quick Start

### 1. Clone and Setup

```bash
cd chat-pdf
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required environment variables:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_role_key_here

# App Configuration
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO
CORS_ORIGINS=*

# Upload & Storage Configuration
MAX_UPLOAD_SIZE_MB=50
UPLOAD_DIR=./uploads
USE_SUPABASE_STORAGE=True
STORAGE_BUCKET_NAME=pdf-uploads

# Embedding Configuration
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# Chat Configuration
CHAT_MODEL=gpt-4o
CHAT_MODEL_MINI=gpt-4o-mini
MAX_CONTEXT_CHUNKS=10
```

### 3. Setup Supabase Database

1. Go to your Supabase project dashboard
2. Navigate to SQL Editor
3. Run the contents of `sql/schema.sql`

This will create:

- Tables: `documents`, `chunks`, `conversations`, `messages`
- Indexes: HNSW vector index, standard B-tree indexes
- RLS policies: Multi-tenant security
- Functions: `match_chunks` for vector similarity search

### 4. Create Storage Bucket (Optional)

If using Supabase Storage instead of local files:

1. Go to Storage in Supabase dashboard
2. Create a new bucket named `pdf-uploads`
3. Set appropriate policies (e.g., authenticated users can upload)

### 5. Run the API Server

```bash
# Development mode with auto-reload
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use the main script
python app/main.py
```

API will be available at: `http://localhost:8000`

- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

### 6. Run the MCP Server

In a separate terminal:

```bash
source venv/bin/activate
python mcp_server/server.py
```

The MCP server uses stdio transport for communication with AI agents/clients.

## API Usage

### Upload a PDF

```bash
curl -X POST "http://localhost:8000/api/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/document.pdf" \
  -F "user_id=00000000-0000-0000-0000-000000000000"
```

Response:

```json
{
  "doc_id": "uuid-here",
  "status": "pending",
  "filename": "document.pdf",
  "message": "File uploaded successfully. Ingestion started."
}
```

### List Documents

```bash
curl "http://localhost:8000/api/documents?user_id=00000000-0000-0000-0000-000000000000&status=ready"
```

### Chat with Documents

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main findings?",
    "doc_ids": ["doc-uuid-1", "doc-uuid-2"]
  }'
```

Response:

```json
{
  "answer": "According to [Source 1], the main findings are...",
  "citations": [
    {
      "doc_id": "uuid",
      "filename": "document.pdf",
      "page_start": 5,
      "page_end": 5,
      "snippet": "The analysis revealed..."
    }
  ],
  "conversation_id": "conv-uuid",
  "message_id": "msg-uuid",
  "token_usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 300,
    "total_tokens": 1500
  }
}
```

## MCP Tools

The MCP server exposes three tools for AI agents:

### `list_docs`

List all documents for a user.

**Input:**

```json
{
  "user_id": "uuid",
  "status": "ready" // optional: pending, processing, ready, failed, all
}
```

### `add_doc`

Upload a PDF from a file path.

**Input:**

```json
{
  "user_id": "uuid",
  "file_path": "/path/to/document.pdf"
}
```

### `chat_with_docs`

Ask a question with document grounding.

**Input:**

```json
{
  "user_id": "uuid",
  "question": "What are the key points?",
  "doc_ids": ["uuid1", "uuid2"],
  "conversation_id": "uuid" // optional
}
```

## Project Structure

```
chat-pdf/
├── app/
│   ├── api/
│   │   └── routes.py          # FastAPI endpoints
│   ├── core/
│   │   └── config.py          # Settings and configuration
│   ├── models/
│   │   └── schemas.py         # Pydantic models
│   ├── services/
│   │   ├── pdf_service.py     # PDF parsing and chunking
│   │   ├── embedding_service.py  # OpenAI embeddings
│   │   ├── supabase_service.py   # Database operations
│   │   ├── ingestion_service.py  # Document ingestion
│   │   └── chat_service.py    # RAG chat
│   └── main.py                # FastAPI app
├── mcp_server/
│   └── server.py              # MCP server
├── supabase/migrations/*      # Database schema
├── uploads/                   # Local file storage
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

Key settings in `.env`:

- **Embedding Model**: `text-embedding-3-small` (1536 dimensions)

  - Upgrade to `text-embedding-3-large` (3072 dims) for better quality
  - Remember to update `EMBEDDING_DIMENSIONS` and pgvector schema

- **Chat Model**: `gpt-4o` (default) or `gpt-4o-mini` (faster/cheaper)

- **Chunking**: 800 tokens per chunk, 150 token overlap

  - Adjust in `pdf_service.py` `chunk_text()` method

- **Retrieval**: Top 10 chunks, 0.7 similarity threshold
  - Adjust in `chat_service.py` and `schema.sql` `match_chunks()` function

## Security

### Row-Level Security (RLS)

All tables have RLS policies enforcing `user_id = auth.uid()`:

- Users can only access their own documents, chunks, conversations, and messages
- Service role key bypasses RLS for server operations

### Best Practices

1. **Production**: Use Supabase Auth JWT for user authentication
2. **API Keys**: Never commit `.env` to version control
3. **Storage**: Use signed URLs (1-hour TTL) for file access
4. **Rate Limiting**: Add middleware for API rate limiting (e.g., slowapi + Redis)

## Cost Estimates

Based on OpenAI pricing (as of 2025):

**Ingestion (per 100-page PDF):**

- Embeddings: ~200 chunks × 800 tokens × $0.02/1M = **$0.0032**
- Total: **~$0.003 per 100-page PDF**

**Chat Query:**

- gpt-4o-mini: ~8k prompt + 300 completion × $0.15-$0.60/1M = **~$0.0014/query**
- gpt-4o: **~$0.01/query** (higher quality)

**Supabase:** Free tier supports up to 500MB database + 1GB storage

## Performance

- **Ingestion**: ~30s for 50-page PDF (parsing + embedding + indexing)
- **Chat**: P95 < 3s (100ms vector search + 1-2s LLM)
- **Scalability**: HNSW index handles <1M vectors efficiently

## Troubleshooting

### Dependencies Won't Install

If llama-index has conflicts, use the simplified `requirements.txt` provided (without llama-index/llama-parse).

### Database Connection Errors

1. Check `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`
2. Verify pgvector extension is enabled: `CREATE EXTENSION vector;`
3. Ensure RLS policies are created (run `schema.sql`)

### Ingestion Fails

1. Check logs for specific errors
2. Verify PDF is not scanned/image-only (use OCR-enabled parser)
3. Check OpenAI API key and quotas
4. Ensure `uploads/` directory exists and is writable

### Vector Search Returns No Results

1. Check similarity threshold (0.7 default, lower if needed)
2. Verify chunks exist: `SELECT COUNT(*) FROM chunks WHERE doc_id = 'uuid';`
3. Test embedding: Ensure dimensions match (1536 for text-embedding-3-small)

## Development

### Run Tests

```bash
pytest tests/
```

### Format Code

```bash
black app/ mcp_server/
```

### Linting

```bash
ruff check app/ mcp_server/
```

## Roadmap

See [APPROACH.md](APPROACH.md) for the full architecture and phased delivery plan.

### V1 (Current)

- ✅ Single-file upload
- ✅ PDF parsing and chunking
- ✅ OpenAI embeddings
- ✅ Vector search with pgvector
- ✅ RAG chat with citations
- ✅ MCP server (stdio)

### V1.1 (Next)

- Multi-file selection
- SHA256 deduplication
- Storage cleanup
- URL-based document ingestion
- Pagination improvements

### V1.2 (Future)

- Hybrid search (FTS + vector)
- Optional reranker (Cohere)
- Batch upload UI
- Streaming chat responses (SSE)
- Advanced citation snippets

## License

MIT

## Support

For issues, see [GitHub Issues](https://github.com/your-repo/chat-pdf/issues)
