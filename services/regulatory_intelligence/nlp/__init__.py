"""
Regulatory Intelligence NLP Pipeline
=====================================

Comprehensive NLP pipeline for regulatory document processing.

Modules:
- extraction: Document extraction (PDF, HTML, text)
- preprocessing: Text cleaning and normalization
- chunking: Smart document chunking for LLM processing
- parser: LLM-based requirement extraction
- rml: Regulatory Markup Language generation
- embeddings: Vector embeddings for semantic search

Version: 0.1.0
"""

from services.regulatory_intelligence.nlp.chunking import (
    Chunk,
    ChunkingStrategy,
    DocumentChunker,
)
from services.regulatory_intelligence.nlp.extraction import (
    DocumentExtractor,
    ExtractionResult,
)
from services.regulatory_intelligence.nlp.parser import (
    ParsedRegulation,
    ParsedRequirement,
    RegulatoryParser,
)
from services.regulatory_intelligence.nlp.preprocessing import (
    PreprocessedDocument,
    TextPreprocessor,
)
from services.regulatory_intelligence.nlp.rml import (
    RMLDocument,
    RMLGenerator,
)


__all__ = [
    # Extraction
    "DocumentExtractor",
    "ExtractionResult",
    # Preprocessing
    "TextPreprocessor",
    "PreprocessedDocument",
    # Chunking
    "DocumentChunker",
    "Chunk",
    "ChunkingStrategy",
    # Parser
    "RegulatoryParser",
    "ParsedRequirement",
    "ParsedRegulation",
    # RML
    "RMLGenerator",
    "RMLDocument",
]
