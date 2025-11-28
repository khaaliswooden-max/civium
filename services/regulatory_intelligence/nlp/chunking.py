"""
Document Chunking Module
========================

Smart chunking strategies for processing large regulatory documents
with LLMs that have context window limits.

Strategies:
- Semantic: Chunk by meaning/topic boundaries
- Structural: Chunk by document structure (sections, articles)
- Fixed: Simple fixed-size chunks with overlap
- Recursive: Hierarchical chunking with fallback

Version: 0.1.0
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from shared.logging import get_logger

logger = get_logger(__name__)


class ChunkingStrategy(str, Enum):
    """Available chunking strategies."""

    SEMANTIC = "semantic"
    STRUCTURAL = "structural"
    FIXED = "fixed"
    RECURSIVE = "recursive"
    SENTENCE = "sentence"


@dataclass
class Chunk:
    """A document chunk for LLM processing."""

    content: str
    index: int
    total_chunks: int

    # Position in original document
    start_char: int
    end_char: int

    # Metadata
    section_number: str | None = None
    section_title: str | None = None

    # Token estimation (approximate)
    estimated_tokens: int = 0

    # For overlap tracking
    overlap_with_previous: int = 0
    overlap_with_next: int = 0

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        """Character count of the chunk."""
        return len(self.content)

    @property
    def word_count(self) -> int:
        """Word count of the chunk."""
        return len(self.content.split())


class DocumentChunker:
    """
    Chunks documents for LLM processing.

    Handles:
    - Multiple chunking strategies
    - Token counting and limits
    - Overlap management
    - Context preservation
    """

    # Approximate tokens per character (conservative estimate)
    CHARS_PER_TOKEN = 4

    # Section break patterns
    SECTION_PATTERNS = [
        re.compile(r"\n(?=(?:CHAPTER|ARTICLE|SECTION|PART)\s+\d)", re.IGNORECASE),
        re.compile(r"\n(?=\d+\.\d+\.?\d*\s+[A-Z])"),
        re.compile(r"\n{2,}(?=[A-Z][a-z])"),
    ]

    # Sentence end pattern
    SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

    def __init__(
        self,
        strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
        max_chunk_size: int = 4000,
        overlap_size: int = 200,
        min_chunk_size: int = 100,
    ) -> None:
        """
        Initialize the chunker.

        Args:
            strategy: Chunking strategy to use
            max_chunk_size: Maximum chunk size in characters
            overlap_size: Overlap between chunks in characters
            min_chunk_size: Minimum chunk size in characters
        """
        self.strategy = strategy
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.min_chunk_size = min_chunk_size

    def chunk(self, text: str, metadata: dict[str, Any] | None = None) -> list[Chunk]:
        """
        Chunk the document using the configured strategy.

        Args:
            text: Document text to chunk
            metadata: Optional metadata to include in chunks

        Returns:
            List of Chunk objects
        """
        if not text.strip():
            return []

        # Choose strategy
        if self.strategy == ChunkingStrategy.STRUCTURAL:
            chunks = self._chunk_structural(text)
        elif self.strategy == ChunkingStrategy.SEMANTIC:
            chunks = self._chunk_semantic(text)
        elif self.strategy == ChunkingStrategy.SENTENCE:
            chunks = self._chunk_sentence(text)
        elif self.strategy == ChunkingStrategy.FIXED:
            chunks = self._chunk_fixed(text)
        else:  # RECURSIVE
            chunks = self._chunk_recursive(text)

        # Add metadata to all chunks
        if metadata:
            for chunk in chunks:
                chunk.metadata.update(metadata)

        # Update total_chunks
        total = len(chunks)
        for chunk in chunks:
            chunk.total_chunks = total
            chunk.estimated_tokens = self._estimate_tokens(chunk.content)

        logger.debug(
            "document_chunked",
            strategy=self.strategy.value,
            chunks=len(chunks),
            avg_size=sum(c.char_count for c in chunks) // len(chunks) if chunks else 0,
        )

        return chunks

    def _chunk_structural(self, text: str) -> list[Chunk]:
        """
        Chunk by document structure (sections, articles).

        Respects regulatory document hierarchy.
        """
        chunks: list[Chunk] = []

        # Find all section boundaries
        boundaries = [0]
        for pattern in self.SECTION_PATTERNS:
            for match in pattern.finditer(text):
                boundaries.append(match.start())
        boundaries.append(len(text))
        boundaries = sorted(set(boundaries))

        # Create chunks from boundaries
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            content = text[start:end].strip()

            if len(content) < self.min_chunk_size:
                # Merge with next chunk if too small
                continue

            if len(content) > self.max_chunk_size:
                # Split large sections recursively
                sub_chunks = self._chunk_recursive(content)
                for sub_chunk in sub_chunks:
                    sub_chunk.start_char += start
                    sub_chunk.end_char += start
                chunks.extend(sub_chunks)
            else:
                # Extract section info
                section_match = re.match(
                    r"(?:CHAPTER|ARTICLE|SECTION|PART)\s+(\d+(?:\.\d+)*)",
                    content,
                    re.IGNORECASE,
                )
                section_number = section_match.group(1) if section_match else None

                chunks.append(
                    Chunk(
                        content=content,
                        index=len(chunks),
                        total_chunks=0,
                        start_char=start,
                        end_char=end,
                        section_number=section_number,
                    )
                )

        return self._reindex_chunks(chunks)

    def _chunk_semantic(self, text: str) -> list[Chunk]:
        """
        Chunk by semantic boundaries.

        Uses paragraph breaks and topic shifts.
        """
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r"\n{2,}", text)
        chunks: list[Chunk] = []
        current_chunk = ""
        current_start = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Would adding this paragraph exceed max size?
            if len(current_chunk) + len(para) + 2 > self.max_chunk_size:
                if current_chunk:
                    chunks.append(
                        Chunk(
                            content=current_chunk,
                            index=len(chunks),
                            total_chunks=0,
                            start_char=current_start,
                            end_char=current_start + len(current_chunk),
                        )
                    )
                    current_start = current_start + len(current_chunk) + 2
                    current_chunk = para
                else:
                    # Single paragraph too large, use recursive
                    sub_chunks = self._chunk_recursive(para)
                    for sub_chunk in sub_chunks:
                        sub_chunk.start_char += current_start
                        sub_chunk.end_char += current_start
                    chunks.extend(sub_chunks)
                    current_start += len(para) + 2
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Add final chunk
        if current_chunk:
            chunks.append(
                Chunk(
                    content=current_chunk,
                    index=len(chunks),
                    total_chunks=0,
                    start_char=current_start,
                    end_char=current_start + len(current_chunk),
                )
            )

        return self._reindex_chunks(chunks)

    def _chunk_sentence(self, text: str) -> list[Chunk]:
        """
        Chunk by sentences, grouping to target size.
        """
        # Split into sentences
        sentences = self.SENTENCE_END.split(text)
        chunks: list[Chunk] = []
        current_chunk = ""
        current_start = 0
        current_pos = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current_chunk) + len(sentence) + 1 > self.max_chunk_size:
                if current_chunk:
                    chunks.append(
                        Chunk(
                            content=current_chunk,
                            index=len(chunks),
                            total_chunks=0,
                            start_char=current_start,
                            end_char=current_pos,
                        )
                    )
                    current_start = current_pos
                    current_chunk = sentence
                else:
                    # Single sentence too large, force split
                    current_chunk = sentence[: self.max_chunk_size]

                current_pos += len(sentence) + 1
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                current_pos += len(sentence) + 1

        if current_chunk:
            chunks.append(
                Chunk(
                    content=current_chunk,
                    index=len(chunks),
                    total_chunks=0,
                    start_char=current_start,
                    end_char=current_pos,
                )
            )

        return self._reindex_chunks(chunks)

    def _chunk_fixed(self, text: str) -> list[Chunk]:
        """
        Simple fixed-size chunking with overlap.
        """
        chunks: list[Chunk] = []
        pos = 0

        while pos < len(text):
            end = min(pos + self.max_chunk_size, len(text))

            # Try to end at a sentence or word boundary
            if end < len(text):
                # Look for sentence end
                sentence_match = re.search(r"[.!?]\s+", text[pos:end][::-1])
                if sentence_match:
                    end = end - sentence_match.start()
                else:
                    # Fall back to word boundary
                    space_pos = text.rfind(" ", pos, end)
                    if space_pos > pos:
                        end = space_pos

            content = text[pos:end].strip()

            if content:
                chunks.append(
                    Chunk(
                        content=content,
                        index=len(chunks),
                        total_chunks=0,
                        start_char=pos,
                        end_char=end,
                        overlap_with_previous=self.overlap_size if pos > 0 else 0,
                    )
                )

            # Move position with overlap
            pos = end - self.overlap_size if end < len(text) else len(text)

        return self._reindex_chunks(chunks)

    def _chunk_recursive(self, text: str) -> list[Chunk]:
        """
        Recursive chunking with multiple split strategies.

        Tries progressively finer-grained splits until chunks fit.
        """
        if len(text) <= self.max_chunk_size:
            return [
                Chunk(
                    content=text.strip(),
                    index=0,
                    total_chunks=1,
                    start_char=0,
                    end_char=len(text),
                )
            ]

        # Try different separators in order of preference
        separators = [
            r"\n{2,}",  # Double newline (paragraphs)
            r"\n(?=(?:CHAPTER|ARTICLE|SECTION|PART)\s)",  # Section headers
            r"\n(?=\d+\.\s)",  # Numbered items
            r"\n",  # Single newline
            r"(?<=[.!?])\s+",  # Sentence end
            r"\s+",  # Any whitespace
        ]

        for sep in separators:
            parts = re.split(sep, text)
            if len(parts) > 1:
                chunks: list[Chunk] = []
                current_chunk = ""
                current_start = 0
                pos = 0

                for part in parts:
                    if len(current_chunk) + len(part) + 1 <= self.max_chunk_size:
                        if current_chunk:
                            current_chunk += "\n" + part
                        else:
                            current_chunk = part
                        pos += len(part) + 1
                    else:
                        if current_chunk:
                            chunks.append(
                                Chunk(
                                    content=current_chunk.strip(),
                                    index=len(chunks),
                                    total_chunks=0,
                                    start_char=current_start,
                                    end_char=current_start + len(current_chunk),
                                )
                            )
                            current_start = pos

                        # If single part is still too large, recurse
                        if len(part) > self.max_chunk_size:
                            sub_chunks = self._chunk_recursive(part)
                            for sub_chunk in sub_chunks:
                                sub_chunk.start_char += current_start
                                sub_chunk.end_char += current_start
                            chunks.extend(sub_chunks)
                            current_chunk = ""
                            current_start = pos + len(part)
                        else:
                            current_chunk = part

                        pos += len(part) + 1

                if current_chunk.strip():
                    chunks.append(
                        Chunk(
                            content=current_chunk.strip(),
                            index=len(chunks),
                            total_chunks=0,
                            start_char=current_start,
                            end_char=current_start + len(current_chunk),
                        )
                    )

                if chunks:
                    return self._reindex_chunks(chunks)

        # Fallback: force split
        return self._chunk_fixed(text)

    def _reindex_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Reindex chunks after processing."""
        for i, chunk in enumerate(chunks):
            chunk.index = i
            chunk.total_chunks = len(chunks)
        return chunks

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(text) // self.CHARS_PER_TOKEN

    def merge_chunks(self, chunks: list[Chunk], max_size: int | None = None) -> list[Chunk]:
        """
        Merge small adjacent chunks.

        Args:
            chunks: Chunks to potentially merge
            max_size: Maximum merged chunk size (default: self.max_chunk_size)

        Returns:
            Merged chunks
        """
        if not chunks:
            return []

        max_size = max_size or self.max_chunk_size
        merged: list[Chunk] = []
        current: Chunk | None = None

        for chunk in chunks:
            if current is None:
                current = chunk
            elif len(current.content) + len(chunk.content) + 2 <= max_size:
                # Merge
                current = Chunk(
                    content=current.content + "\n\n" + chunk.content,
                    index=current.index,
                    total_chunks=0,
                    start_char=current.start_char,
                    end_char=chunk.end_char,
                    section_number=current.section_number,
                    section_title=current.section_title,
                )
            else:
                merged.append(current)
                current = chunk

        if current:
            merged.append(current)

        return self._reindex_chunks(merged)

