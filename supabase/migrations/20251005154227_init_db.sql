-- Chat PDF Database Schema
-- This schema is designed for Supabase (PostgreSQL + pgvector)

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    sha256 TEXT NOT NULL,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    page_count INTEGER,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes on documents
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_user_status ON documents(user_id, status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);

-- Create unique constraint on sha256 per user (allow same file for different users)
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_user_sha256 ON documents(user_id, sha256, version);

-- Chunks table with vector embeddings
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,  -- OpenAI text-embedding-3-small dimensions
    page_start INTEGER,
    page_end INTEGER,
    section TEXT,
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes on chunks
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);

-- Create HNSW index for vector similarity search (better for < 1M vectors)
-- Parameters: m=16 (connections per layer), ef_construction=64 (search quality during build)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
ON chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Alternative: IVFFlat index (better for > 1M vectors, faster writes)
-- Uncomment if dataset grows large
-- CREATE INDEX idx_chunks_embedding_ivfflat
-- ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index on conversations
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    doc_ids UUID[],  -- Array of document IDs used for this query
    citations JSONB,  -- Array of citation objects
    token_usage JSONB,  -- {prompt: N, completion: N, total: N}
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes on messages
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- Row Level Security (RLS) Policies
-- Enable RLS on all tables
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Documents RLS Policies
CREATE POLICY "Users can view their own documents"
    ON documents FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own documents"
    ON documents FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own documents"
    ON documents FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own documents"
    ON documents FOR DELETE
    USING (auth.uid() = user_id);

-- Chunks RLS Policies (inherit from documents)
CREATE POLICY "Users can view chunks of their documents"
    ON chunks FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM documents
            WHERE documents.id = chunks.doc_id
            AND documents.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role can insert chunks"
    ON chunks FOR INSERT
    WITH CHECK (true);  -- Service key bypasses RLS, but policy must exist

CREATE POLICY "Service role can update chunks"
    ON chunks FOR UPDATE
    USING (true);

CREATE POLICY "Users can delete chunks of their documents"
    ON chunks FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM documents
            WHERE documents.id = chunks.doc_id
            AND documents.user_id = auth.uid()
        )
    );

-- Conversations RLS Policies
CREATE POLICY "Users can view their own conversations"
    ON conversations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own conversations"
    ON conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own conversations"
    ON conversations FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own conversations"
    ON conversations FOR DELETE
    USING (auth.uid() = user_id);

-- Messages RLS Policies (inherit from conversations)
CREATE POLICY "Users can view messages in their conversations"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM conversations
            WHERE conversations.id = messages.conversation_id
            AND conversations.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert messages in their conversations"
    ON messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM conversations
            WHERE conversations.id = messages.conversation_id
            AND conversations.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update messages in their conversations"
    ON messages FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM conversations
            WHERE conversations.id = messages.conversation_id
            AND conversations.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete messages in their conversations"
    ON messages FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM conversations
            WHERE conversations.id = messages.conversation_id
            AND conversations.user_id = auth.uid()
        )
    );

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on documents
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function for vector similarity search with metadata filtering
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(1536),
    filter_doc_ids UUID[],
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    doc_id UUID,
    content TEXT,
    page_start INTEGER,
    page_end INTEGER,
    section TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        chunks.id,
        chunks.doc_id,
        chunks.content,
        chunks.page_start,
        chunks.page_end,
        chunks.section,
        1 - (chunks.embedding <=> query_embedding) AS similarity
    FROM chunks
    WHERE
        chunks.doc_id = ANY(filter_doc_ids)
        AND 1 - (chunks.embedding <=> query_embedding) > match_threshold
    ORDER BY chunks.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Grant permissions (adjust as needed for your setup)
-- Note: In Supabase, service_role bypasses RLS automatically
-- These grants are for authenticated users through RLS policies
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;
