"""
Embeddings Module
=================

Vector embeddings for semantic search of regulatory requirements.

Features:
- Multiple embedding providers (OpenAI, Cohere, local)
- Chunked embedding for long documents
- Similarity search utilities
- Batch processing

Version: 0.1.0
"""

import asyncio
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import httpx

from shared.config import settings
from shared.logging import get_logger


logger = get_logger(__name__)


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""

    OPENAI = "openai"
    COHERE = "cohere"
    SENTENCE_TRANSFORMERS = "sentence_transformers"


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""

    text: str
    embedding: list[float]
    model: str
    provider: EmbeddingProvider

    # Metadata
    text_hash: str = ""
    token_count: int = 0
    dimensions: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Compute derived fields."""
        if not self.text_hash:
            self.text_hash = hashlib.md5(self.text.encode()).hexdigest()
        if not self.dimensions:
            self.dimensions = len(self.embedding)


@dataclass
class SimilarityResult:
    """Result of similarity search."""

    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def provider_name(self) -> EmbeddingProvider:
        """Provider identifier."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier."""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding dimensions."""
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        ...


class OpenAIEmbeddings(BaseEmbeddingProvider):
    """
    OpenAI embeddings provider.

    Uses text-embedding-3-small or text-embedding-3-large.
    """

    MODELS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
    ) -> None:
        """
        Initialize OpenAI embeddings.

        Args:
            api_key: OpenAI API key
            model: Model to use
        """
        self._api_key = api_key or settings.llm.openai.api_key.get_secret_value()
        self._model = model
        self._client: httpx.AsyncClient | None = None

        if not self._api_key:
            raise ValueError("OpenAI API key required for embeddings")

    @property
    def provider_name(self) -> EmbeddingProvider:
        return EmbeddingProvider.OPENAI

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self.MODELS.get(self._model, 1536)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.openai.com/v1",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        client = await self._get_client()

        # OpenAI has a limit of 8191 tokens per text
        # Truncate very long texts
        processed_texts = [text[:30000] for text in texts]

        response = await client.post(
            "/embeddings",
            json={
                "model": self._model,
                "input": processed_texts,
            },
        )
        response.raise_for_status()

        data = response.json()
        embeddings = [item["embedding"] for item in data["data"]]

        logger.debug(
            "openai_embeddings_generated",
            count=len(embeddings),
            model=self._model,
        )

        return embeddings

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class CohereEmbeddings(BaseEmbeddingProvider):
    """
    Cohere embeddings provider.

    Uses embed-english-v3.0 or embed-multilingual-v3.0.
    """

    MODELS = {
        "embed-english-v3.0": 1024,
        "embed-multilingual-v3.0": 1024,
        "embed-english-light-v3.0": 384,
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "embed-english-v3.0",
    ) -> None:
        """
        Initialize Cohere embeddings.

        Args:
            api_key: Cohere API key
            model: Model to use
        """
        self._api_key = api_key
        self._model = model
        self._client: httpx.AsyncClient | None = None

        if not self._api_key:
            raise ValueError("Cohere API key required")

    @property
    def provider_name(self) -> EmbeddingProvider:
        return EmbeddingProvider.COHERE

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self.MODELS.get(self._model, 1024)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.cohere.ai/v1",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        client = await self._get_client()

        response = await client.post(
            "/embed",
            json={
                "model": self._model,
                "texts": texts,
                "input_type": "search_document",
            },
        )
        response.raise_for_status()

        data = response.json()
        return data["embeddings"]

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class LocalEmbeddings(BaseEmbeddingProvider):
    """
    Local embeddings using sentence-transformers.

    Runs entirely locally without API calls.
    """

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        """
        Initialize local embeddings.

        Args:
            model: Sentence-transformers model name
        """
        self._model_name = model
        self._model: Any = None
        self._dimensions: int = 384  # Default for MiniLM

    @property
    def provider_name(self) -> EmbeddingProvider:
        return EmbeddingProvider.SENTENCE_TRANSFORMERS

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _load_model(self) -> Any:
        """Load the sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._model_name)
                self._dimensions = self._model.get_sentence_embedding_dimension()
            except ImportError:
                raise ImportError(
                    "sentence-transformers required for local embeddings. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        model = self._load_model()
        # Run in thread pool for async compatibility
        embedding = await asyncio.to_thread(
            model.encode,
            text,
            convert_to_numpy=True,
        )
        return embedding.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        model = self._load_model()
        embeddings = await asyncio.to_thread(
            model.encode,
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()


class EmbeddingService:
    """
    High-level embedding service.

    Handles:
    - Provider selection
    - Caching
    - Batch processing
    - Similarity computation
    """

    def __init__(
        self,
        provider: BaseEmbeddingProvider | None = None,
        cache_enabled: bool = True,
    ) -> None:
        """
        Initialize embedding service.

        Args:
            provider: Embedding provider (default: OpenAI if API key available)
            cache_enabled: Whether to cache embeddings
        """
        if provider is None:
            # Try OpenAI first
            if settings.llm.openai.api_key.get_secret_value():
                provider = OpenAIEmbeddings()
            else:
                # Fall back to local
                provider = LocalEmbeddings()

        self.provider = provider
        self.cache_enabled = cache_enabled
        self._cache: dict[str, list[float]] = {}

    async def embed_text(self, text: str) -> EmbeddingResult:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            EmbeddingResult with vector
        """
        text_hash = hashlib.md5(text.encode()).hexdigest()

        # Check cache
        if self.cache_enabled and text_hash in self._cache:
            return EmbeddingResult(
                text=text,
                embedding=self._cache[text_hash],
                model=self.provider.model_name,
                provider=self.provider.provider_name,
                text_hash=text_hash,
            )

        # Generate embedding
        embedding = await self.provider.embed(text)

        # Cache result
        if self.cache_enabled:
            self._cache[text_hash] = embedding

        return EmbeddingResult(
            text=text,
            embedding=embedding,
            model=self.provider.model_name,
            provider=self.provider.provider_name,
            text_hash=text_hash,
        )

    async def embed_texts(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[EmbeddingResult]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: Texts to embed
            batch_size: Batch size for API calls

        Returns:
            List of EmbeddingResults
        """
        results: list[EmbeddingResult] = []

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # Check cache for each text
            to_embed: list[tuple[int, str]] = []
            batch_results: list[EmbeddingResult | None] = [None] * len(batch)

            for j, text in enumerate(batch):
                text_hash = hashlib.md5(text.encode()).hexdigest()
                if self.cache_enabled and text_hash in self._cache:
                    batch_results[j] = EmbeddingResult(
                        text=text,
                        embedding=self._cache[text_hash],
                        model=self.provider.model_name,
                        provider=self.provider.provider_name,
                        text_hash=text_hash,
                    )
                else:
                    to_embed.append((j, text))

            # Embed uncached texts
            if to_embed:
                indices, texts_to_embed = zip(*to_embed)
                embeddings = await self.provider.embed_batch(list(texts_to_embed))

                for idx, (j, text) in enumerate(to_embed):
                    text_hash = hashlib.md5(text.encode()).hexdigest()
                    embedding = embeddings[idx]

                    if self.cache_enabled:
                        self._cache[text_hash] = embedding

                    batch_results[j] = EmbeddingResult(
                        text=text,
                        embedding=embedding,
                        model=self.provider.model_name,
                        provider=self.provider.provider_name,
                        text_hash=text_hash,
                    )

            results.extend([r for r in batch_results if r is not None])

        return results

    def cosine_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Similarity score between -1 and 1
        """
        import math

        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = math.sqrt(sum(a * a for a in embedding1))
        norm2 = math.sqrt(sum(b * b for b in embedding2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def find_similar(
        self,
        query: str,
        documents: list[tuple[str, dict[str, Any]]],
        top_k: int = 10,
        threshold: float = 0.5,
    ) -> list[SimilarityResult]:
        """
        Find documents similar to query.

        Args:
            query: Query text
            documents: List of (text, metadata) tuples
            top_k: Number of results to return
            threshold: Minimum similarity threshold

        Returns:
            List of SimilarityResults sorted by score
        """
        # Embed query
        query_result = await self.embed_text(query)

        # Embed documents
        texts = [text for text, _ in documents]
        doc_results = await self.embed_texts(texts)

        # Compute similarities
        similarities: list[SimilarityResult] = []
        for doc_result, (text, metadata) in zip(doc_results, documents):
            score = self.cosine_similarity(
                query_result.embedding,
                doc_result.embedding,
            )

            if score >= threshold:
                similarities.append(
                    SimilarityResult(
                        text=text,
                        score=score,
                        metadata=metadata,
                    )
                )

        # Sort by score and return top_k
        similarities.sort(key=lambda x: x.score, reverse=True)
        return similarities[:top_k]

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()
