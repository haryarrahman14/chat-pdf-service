"""RAG chat service using OpenAI"""

from typing import List, Dict, Any, Tuple
import logging
from openai import AsyncOpenAI
from app.core.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.supabase_service import SupabaseService
from app.models.schemas import Citation

logger = logging.getLogger(__name__)


class ChatService:
    """Service for RAG-based chat with document grounding"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.embedding_service = EmbeddingService()
        self.db_service = SupabaseService()

    async def chat(
        self,
        question: str,
        doc_ids: List[str],
        model: str = None,
        max_chunks: int = None,
    ) -> Tuple[str, List[Citation], Dict[str, int]]:
        """
        Process a chat query with RAG

        Args:
            question: User's question
            doc_ids: List of document IDs to search
            model: OpenAI model to use (defaults to settings.chat_model)
            max_chunks: Maximum number of chunks to retrieve

        Returns:
            Tuple of (answer, citations, token_usage)
        """
        model = model or settings.chat_model
        max_chunks = max_chunks or settings.max_context_chunks

        # 1. Generate embedding for the question
        question_embedding = await self.embedding_service.generate_embedding(question)

        # 2. Retrieve relevant chunks with multiple thresholds for better recall
        chunks = await self.db_service.search_chunks(
            query_embedding=question_embedding,
            doc_ids=doc_ids,
            match_threshold=0.5,  # Lowered from 0.7 for better recall
            match_count=max_chunks,
        )

        # Fallback: if no chunks found, try with even lower threshold
        if not chunks:
            chunks = await self.db_service.search_chunks(
                query_embedding=question_embedding,
                doc_ids=doc_ids,
                match_threshold=0.3,
                match_count=max_chunks,
            )

        if not chunks:
            return (
                "I don't have enough information in the selected documents to answer that question.",
                [],
                {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            )

        # 3. Build context from retrieved chunks
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            page_info = ""
            if chunk.get("page_start"):
                if chunk.get("page_end") and chunk["page_end"] != chunk["page_start"]:
                    page_info = f" (Pages {chunk['page_start']}-{chunk['page_end']})"
                else:
                    page_info = f" (Page {chunk['page_start']})"

            context_parts.append(f"[Source {i}]{page_info}:\n{chunk['content']}\n")

        context = "\n".join(context_parts)

        # 4. Build system prompt
        system_prompt = """You are a helpful assistant that answers questions strictly based on the provided document excerpts.

IMPORTANT RULES:
1. Only use information from the provided sources to answer questions
2. If the answer is not in the sources, clearly state: "I don't have enough information in the selected documents to answer that question."
3. Always cite your sources using the [Source N] format when making claims
4. Be concise but comprehensive
5. If multiple sources support a claim, cite all relevant sources
6. Do not make up information or use external knowledge

When citing sources, use the format: "According to [Source 1], ..." or "... [Source 2, Source 3]"
"""

        # 5. Build user prompt
        user_prompt = f"""Context from documents:

{context}

Question: {question}

Please answer the question based only on the context provided above. Remember to cite your sources."""

        # 6. Call OpenAI
        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # Lower temperature for more factual responses
            max_tokens=1000,
        )

        answer = response.choices[0].message.content

        # 7. Extract token usage
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

        # 8. Build citations from chunks
        citations = await self._build_citations(chunks, doc_ids)

        return answer, citations, token_usage

    async def _build_citations(
        self, chunks: List[Dict[str, Any]], doc_ids: List[str]
    ) -> List[Citation]:
        """Build citation objects from chunks"""
        citations = []
        seen_docs = set()

        # Get document info for all doc_ids
        doc_info = {}
        for doc_id in doc_ids:
            doc = await self.db_service.get_document(doc_id)
            if doc:
                doc_info[doc_id] = doc

        # Build citations from chunks
        for chunk in chunks:
            doc_id = chunk["doc_id"]

            seen_docs.add(doc_id)

            # Get document info
            doc = doc_info.get(doc_id)
            if not doc:
                continue

            # Create citation
            snippet = (
                chunk["content"][:197] + "..."
                if len(chunk["content"]) > 197
                else chunk["content"]
            )

            citation = Citation(
                doc_id=doc_id,
                filename=doc["filename"],
                page_start=chunk.get("page_start"),
                page_end=chunk.get("page_end"),
                snippet=snippet,
            )

            citations.append(citation)

        return citations
