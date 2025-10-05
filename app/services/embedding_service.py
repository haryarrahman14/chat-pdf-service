"""Embedding generation service using OpenAI"""
from typing import List
from openai import AsyncOpenAI
from app.core.config import settings


class EmbeddingService:
    """Service for generating embeddings using OpenAI"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions
        )

        return response.data[0].embedding

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches

        Args:
            texts: List of input texts
            batch_size: Number of texts to process in each batch (max 8192 for OpenAI)

        Returns:
            List of embedding vectors
        """
        all_embeddings = []

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            response = await self.client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimensions
            )

            # Extract embeddings in order
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings
