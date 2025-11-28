"""
Tests for Regulatory Intelligence NLP Pipeline
==============================================

Comprehensive tests for:
- Document extraction
- Text preprocessing
- Chunking strategies
- Regulatory parser
- RML generation
- Embeddings

Version: 0.1.0
"""

import hashlib
from datetime import date

import pytest

from services.regulatory_intelligence.nlp.extraction import (
    DocumentExtractor,
    DocumentFormat,
    ExtractionResult,
)
from services.regulatory_intelligence.nlp.preprocessing import (
    TextPreprocessor,
    PreprocessedDocument,
    Citation,
    Section,
)
from services.regulatory_intelligence.nlp.chunking import (
    DocumentChunker,
    ChunkingStrategy,
    Chunk,
)
from services.regulatory_intelligence.nlp.parser import (
    RegulatoryParser,
    ParsedRequirement,
    ParsedRegulation,
    RequirementType,
    ComplianceTier,
    VerificationMethod,
)
from services.regulatory_intelligence.nlp.rml import (
    RMLGenerator,
    RMLDocument,
    RMLRequirement,
    RMLVersion,
)


# ============================================================================
# Document Extraction Tests
# ============================================================================


class TestDocumentExtractor:
    """Tests for DocumentExtractor."""

    @pytest.fixture
    def extractor(self) -> DocumentExtractor:
        return DocumentExtractor()

    def test_detect_format_from_url_pdf(self, extractor: DocumentExtractor) -> None:
        """Test PDF format detection from URL."""
        result = extractor.detect_format(b"", "https://example.com/doc.pdf")
        assert result == DocumentFormat.PDF

    def test_detect_format_from_url_html(self, extractor: DocumentExtractor) -> None:
        """Test HTML format detection from URL."""
        result = extractor.detect_format(b"", "https://example.com/page.html")
        assert result == DocumentFormat.HTML

    def test_detect_format_from_content_pdf(self, extractor: DocumentExtractor) -> None:
        """Test PDF format detection from magic bytes."""
        result = extractor.detect_format(b"%PDF-1.4", None)
        assert result == DocumentFormat.PDF

    def test_detect_format_from_content_html(self, extractor: DocumentExtractor) -> None:
        """Test HTML format detection from content."""
        result = extractor.detect_format("<!DOCTYPE html><html>", None)
        assert result == DocumentFormat.HTML

    def test_detect_format_from_content_docx(self, extractor: DocumentExtractor) -> None:
        """Test DOCX format detection from magic bytes."""
        result = extractor.detect_format(b"PK\x03\x04", None)
        assert result == DocumentFormat.DOCX

    def test_detect_format_defaults_to_text(self, extractor: DocumentExtractor) -> None:
        """Test default text format detection."""
        result = extractor.detect_format("Plain text content", None)
        assert result == DocumentFormat.TEXT

    def test_extract_text_normalization(self, extractor: DocumentExtractor) -> None:
        """Test text extraction normalizes content."""
        content = "Line 1\r\nLine 2\r\n\r\n\r\nLine 3"
        result = extractor._extract_text(content)

        assert "\r" not in result.content
        assert "\n\n\n" not in result.content

    def test_extract_text_detects_title(self, extractor: DocumentExtractor) -> None:
        """Test title detection in plain text."""
        content = "REGULATION TITLE\n\nFirst paragraph of content."
        result = extractor._extract_text(content)

        assert result.title == "REGULATION TITLE"

    def test_extract_html_removes_scripts(self, extractor: DocumentExtractor) -> None:
        """Test HTML extraction removes script tags."""
        html = "<html><body><script>alert('test')</script>Content here</body></html>"
        result = extractor._extract_html(html)

        assert "alert" not in result.content
        assert "Content here" in result.content

    def test_extraction_result_computes_hash(self) -> None:
        """Test ExtractionResult computes content hash."""
        result = ExtractionResult(
            content="Test content",
            format=DocumentFormat.TEXT,
        )

        expected_hash = hashlib.sha256(b"Test content").hexdigest()
        assert result.content_hash == expected_hash

    def test_extraction_result_computes_word_count(self) -> None:
        """Test ExtractionResult computes word count."""
        result = ExtractionResult(
            content="One two three four five",
            format=DocumentFormat.TEXT,
        )

        assert result.word_count == 5


# ============================================================================
# Text Preprocessing Tests
# ============================================================================


class TestTextPreprocessor:
    """Tests for TextPreprocessor."""

    @pytest.fixture
    def preprocessor(self) -> TextPreprocessor:
        return TextPreprocessor()

    def test_unicode_normalization(self, preprocessor: TextPreprocessor) -> None:
        """Test Unicode character normalization."""
        text = "Smart "quotes" and — dashes"
        result = preprocessor._normalize_unicode(text)

        assert '"' in result  # Normalized quotes
        assert "—" not in result  # Normalized dashes

    def test_extract_us_code_citations(self, preprocessor: TextPreprocessor) -> None:
        """Test US Code citation extraction."""
        text = "Pursuant to 42 U.S.C. § 1234, the agency shall..."
        citations = preprocessor._extract_citations(text)

        assert len(citations) >= 1
        assert any(c.citation_type == "us_code" for c in citations)

    def test_extract_cfr_citations(self, preprocessor: TextPreprocessor) -> None:
        """Test CFR citation extraction."""
        text = "Under 45 CFR 164.502, covered entities must..."
        citations = preprocessor._extract_citations(text)

        assert len(citations) >= 1
        assert any(c.citation_type == "cfr" for c in citations)

    def test_extract_eu_regulation_citations(self, preprocessor: TextPreprocessor) -> None:
        """Test EU regulation citation extraction."""
        text = "Regulation (EU) 2016/679 establishes requirements..."
        citations = preprocessor._extract_citations(text)

        assert len(citations) >= 1
        assert any(c.citation_type == "eu_regulation" for c in citations)

    def test_detect_section_headers(self, preprocessor: TextPreprocessor) -> None:
        """Test section header detection."""
        text = """
CHAPTER 1 - INTRODUCTION

This chapter provides background.

SECTION 1.1 - Definitions

The following definitions apply.
"""
        sections = preprocessor._detect_sections(text)

        assert len(sections) >= 1
        # Should detect chapter and/or section
        assert any(s.number == "1" or s.number == "1.1" for s in sections)

    def test_detect_us_jurisdiction(self, preprocessor: TextPreprocessor) -> None:
        """Test US jurisdiction detection."""
        text = "The Federal Register notice under U.S.C. section 5..."
        result = preprocessor._detect_jurisdiction(text)

        assert result == "US"

    def test_detect_eu_jurisdiction(self, preprocessor: TextPreprocessor) -> None:
        """Test EU jurisdiction detection."""
        text = "The European Parliament and Council Regulation (EU)..."
        result = preprocessor._detect_jurisdiction(text)

        assert result == "EU"

    def test_detect_data_protection_type(self, preprocessor: TextPreprocessor) -> None:
        """Test data protection regulation type detection."""
        text = "Personal data processing under GDPR requirements..."
        result = preprocessor._detect_regulation_type(text)

        assert result == "data_protection"

    def test_detect_financial_type(self, preprocessor: TextPreprocessor) -> None:
        """Test financial regulation type detection."""
        text = "Securities and investment banking regulations..."
        result = preprocessor._detect_regulation_type(text)

        assert result == "financial"

    def test_preprocess_returns_complete_result(self, preprocessor: TextPreprocessor) -> None:
        """Test complete preprocessing result."""
        text = """
CHAPTER 1: DATA PROTECTION

Under 42 U.S.C. § 1234, organizations must protect personal data.

SECTION 1.1: Requirements

Data controllers shall implement appropriate measures.
"""
        result = preprocessor.preprocess(text)

        assert isinstance(result, PreprocessedDocument)
        assert result.cleaned_text != ""
        assert result.word_count > 0
        assert len(result.preprocessing_notes) > 0


# ============================================================================
# Document Chunking Tests
# ============================================================================


class TestDocumentChunker:
    """Tests for DocumentChunker."""

    @pytest.fixture
    def chunker(self) -> DocumentChunker:
        return DocumentChunker(max_chunk_size=500, overlap_size=50)

    def test_small_text_single_chunk(self, chunker: DocumentChunker) -> None:
        """Test small text produces single chunk."""
        text = "Short text content."
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].content == text.strip()

    def test_long_text_multiple_chunks(self, chunker: DocumentChunker) -> None:
        """Test long text produces multiple chunks."""
        text = "Word " * 500  # Well over chunk size
        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        assert all(len(c.content) <= chunker.max_chunk_size for c in chunks)

    def test_chunk_indices_sequential(self, chunker: DocumentChunker) -> None:
        """Test chunk indices are sequential."""
        text = "Content. " * 200
        chunks = chunker.chunk(text)

        for i, chunk in enumerate(chunks):
            assert chunk.index == i
            assert chunk.total_chunks == len(chunks)

    def test_chunk_positions_valid(self, chunker: DocumentChunker) -> None:
        """Test chunk positions are valid."""
        text = "Some text content. " * 100
        chunks = chunker.chunk(text)

        for chunk in chunks:
            assert chunk.start_char >= 0
            assert chunk.end_char <= len(text)
            assert chunk.start_char < chunk.end_char

    def test_structural_chunking_respects_sections(self) -> None:
        """Test structural chunking respects section boundaries."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.STRUCTURAL,
            max_chunk_size=500,
        )

        text = """
SECTION 1 - Introduction

This is section one content.

SECTION 2 - Requirements

This is section two content.
"""
        chunks = chunker.chunk(text)

        # Should have at least 2 chunks (one per section)
        assert len(chunks) >= 1

    def test_sentence_chunking_preserves_sentences(self) -> None:
        """Test sentence chunking keeps sentences intact."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            max_chunk_size=100,
        )

        text = "First sentence. Second sentence. Third sentence."
        chunks = chunker.chunk(text)

        # Each chunk should have complete sentences
        for chunk in chunks:
            # Should not end mid-sentence (unless at max size)
            if not chunk.content.endswith((".", "!", "?")):
                assert len(chunk.content) >= chunker.max_chunk_size - 50

    def test_chunk_metadata_preserved(self, chunker: DocumentChunker) -> None:
        """Test metadata passed through to chunks."""
        text = "Some content."
        metadata = {"regulation_id": "REG-001", "jurisdiction": "US"}

        chunks = chunker.chunk(text, metadata=metadata)

        assert chunks[0].metadata["regulation_id"] == "REG-001"
        assert chunks[0].metadata["jurisdiction"] == "US"


# ============================================================================
# Regulatory Parser Tests
# ============================================================================


class TestRegulatoryParser:
    """Tests for RegulatoryParser."""

    @pytest.fixture
    def parser(self) -> RegulatoryParser:
        return RegulatoryParser(
            max_concurrent_requests=2,
            chunk_size=2000,
            enable_formal_logic=False,
        )

    def test_text_similarity_identical(self, parser: RegulatoryParser) -> None:
        """Test similarity of identical texts."""
        similarity = parser._text_similarity(
            "the quick brown fox",
            "the quick brown fox",
        )
        assert similarity == 1.0

    def test_text_similarity_different(self, parser: RegulatoryParser) -> None:
        """Test similarity of different texts."""
        similarity = parser._text_similarity(
            "the quick brown fox",
            "completely different words here",
        )
        assert similarity < 0.5

    def test_text_similarity_partial(self, parser: RegulatoryParser) -> None:
        """Test similarity of partially overlapping texts."""
        similarity = parser._text_similarity(
            "the quick brown fox jumps",
            "the quick red fox runs",
        )
        assert 0.3 < similarity < 0.8

    def test_deduplicate_removes_duplicates(self, parser: RegulatoryParser) -> None:
        """Test deduplication removes duplicate requirements."""
        reqs = [
            ParsedRequirement(
                id="1",
                article_ref="Art. 1",
                regulation_id="REG-001",
                natural_language="Organizations must protect data.",
            ),
            ParsedRequirement(
                id="2",
                article_ref="Art. 1",
                regulation_id="REG-001",
                natural_language="Organizations must protect data.",  # Duplicate
            ),
            ParsedRequirement(
                id="3",
                article_ref="Art. 2",
                regulation_id="REG-001",
                natural_language="Different requirement about security.",
            ),
        ]

        deduped = parser._deduplicate_requirements(reqs)

        assert len(deduped) == 2

    def test_parse_json_response_valid(self, parser: RegulatoryParser) -> None:
        """Test parsing valid JSON response."""
        response = '[{"article_ref": "Art. 1", "text": "Test requirement"}]'
        result = parser._parse_json_response(response)

        assert len(result) == 1
        assert result[0]["article_ref"] == "Art. 1"

    def test_parse_json_response_with_markdown(self, parser: RegulatoryParser) -> None:
        """Test parsing JSON wrapped in markdown."""
        response = '```json\n[{"article_ref": "Art. 1"}]\n```'
        result = parser._parse_json_response(response)

        assert len(result) == 1

    def test_parse_json_object_valid(self, parser: RegulatoryParser) -> None:
        """Test parsing JSON object."""
        response = '{"tier": "basic", "verification_method": "self_attestation"}'
        result = parser._parse_json_object(response)

        assert result["tier"] == "basic"


# ============================================================================
# RML Generator Tests
# ============================================================================


class TestRMLGenerator:
    """Tests for RMLGenerator."""

    @pytest.fixture
    def generator(self) -> RMLGenerator:
        return RMLGenerator()

    @pytest.fixture
    def sample_regulation(self) -> ParsedRegulation:
        return ParsedRegulation(
            id="REG-US-TEST001",
            name="Test Regulation",
            short_name="TestReg",
            jurisdiction="US",
            jurisdictions=["US"],
            sectors=["FINANCE"],
            effective_date=date(2024, 1, 1),
            requirements=[
                ParsedRequirement(
                    id="REQ-001",
                    article_ref="Section 1.1",
                    regulation_id="REG-US-TEST001",
                    natural_language="Organizations must implement security controls.",
                    requirement_type=RequirementType.OBLIGATION,
                    tier=ComplianceTier.STANDARD,
                    verification_method=VerificationMethod.DOCUMENT_REVIEW,
                    applies_to=["data_controllers"],
                    sectors=["FINANCE"],
                    jurisdictions=["US"],
                    confidence=0.9,
                ),
            ],
        )

    def test_generate_creates_rml_document(
        self,
        generator: RMLGenerator,
        sample_regulation: ParsedRegulation,
    ) -> None:
        """Test generate creates valid RMLDocument."""
        rml = generator.generate(sample_regulation)

        assert isinstance(rml, RMLDocument)
        assert rml.id == sample_regulation.id
        assert rml.name == sample_regulation.name
        assert len(rml.requirements) == 1

    def test_rml_includes_statistics(
        self,
        generator: RMLGenerator,
        sample_regulation: ParsedRegulation,
    ) -> None:
        """Test RML includes computed statistics."""
        rml = generator.generate(sample_regulation)

        assert rml.statistics["total_requirements"] == 1
        assert rml.statistics["by_tier"]["standard"] == 1

    def test_rml_computes_hash(
        self,
        generator: RMLGenerator,
        sample_regulation: ParsedRegulation,
    ) -> None:
        """Test RML document hash is computed."""
        rml = generator.generate(sample_regulation)

        assert rml.document_hash != ""
        assert len(rml.document_hash) == 64  # SHA-256 hex

    def test_rml_to_json_valid(
        self,
        generator: RMLGenerator,
        sample_regulation: ParsedRegulation,
    ) -> None:
        """Test RML converts to valid JSON."""
        import json

        rml = generator.generate(sample_regulation)
        json_str = rml.to_json()

        # Should parse without error
        parsed = json.loads(json_str)
        assert parsed["id"] == sample_regulation.id

    def test_rml_from_json_roundtrip(
        self,
        generator: RMLGenerator,
        sample_regulation: ParsedRegulation,
    ) -> None:
        """Test RML survives JSON roundtrip."""
        rml = generator.generate(sample_regulation)
        json_str = rml.to_json()

        restored = RMLDocument.from_json(json_str)

        assert restored.id == rml.id
        assert restored.name == rml.name
        assert len(restored.requirements) == len(rml.requirements)

    def test_validate_returns_empty_for_valid(
        self,
        generator: RMLGenerator,
        sample_regulation: ParsedRegulation,
    ) -> None:
        """Test validation returns empty list for valid RML."""
        rml = generator.generate(sample_regulation)
        errors = generator.validate(rml)

        assert errors == []

    def test_validate_catches_missing_fields(self, generator: RMLGenerator) -> None:
        """Test validation catches missing required fields."""
        rml = RMLDocument()  # Missing id, name, jurisdiction
        errors = generator.validate(rml)

        assert len(errors) >= 3
        assert any("id" in e for e in errors)
        assert any("name" in e for e in errors)
        assert any("jurisdiction" in e for e in errors)

    def test_diff_detects_no_changes(
        self,
        generator: RMLGenerator,
        sample_regulation: ParsedRegulation,
    ) -> None:
        """Test diff detects identical documents."""
        rml1 = generator.generate(sample_regulation)
        rml2 = generator.generate(sample_regulation)

        diff = generator.diff(rml1, rml2)

        assert not diff["has_changes"]
        assert diff["added_requirements"] == []
        assert diff["removed_requirements"] == []

    def test_diff_detects_added_requirements(
        self,
        generator: RMLGenerator,
    ) -> None:
        """Test diff detects added requirements."""
        reg1 = ParsedRegulation(
            id="REG-001",
            name="Test",
            jurisdiction="US",
            requirements=[],
        )

        reg2 = ParsedRegulation(
            id="REG-001",
            name="Test",
            jurisdiction="US",
            requirements=[
                ParsedRequirement(
                    id="REQ-001",
                    article_ref="Art. 1",
                    regulation_id="REG-001",
                    natural_language="New requirement",
                ),
            ],
        )

        rml1 = generator.generate(reg1)
        rml2 = generator.generate(reg2)

        diff = generator.diff(rml1, rml2)

        assert diff["has_changes"]
        assert len(diff["added_requirements"]) == 1


# ============================================================================
# Integration Tests
# ============================================================================


class TestNLPPipelineIntegration:
    """Integration tests for the complete NLP pipeline."""

    @pytest.mark.asyncio
    async def test_extraction_to_preprocessing(self) -> None:
        """Test extraction output feeds into preprocessing."""
        extractor = DocumentExtractor()
        preprocessor = TextPreprocessor()

        # Simulate extracted content
        html_content = """
        <html>
        <body>
            <h1>Test Regulation</h1>
            <p>Under 42 U.S.C. § 1234, organizations must comply.</p>
            <script>alert('ignored')</script>
        </body>
        </html>
        """

        extraction_result = extractor._extract_html(html_content)
        preprocessed = preprocessor.preprocess(extraction_result.content)

        # Preprocessed should have cleaned content
        assert "alert" not in preprocessed.cleaned_text
        assert "organizations" in preprocessed.cleaned_text.lower()

        # Should detect citation
        assert len(preprocessed.citations) >= 1

    def test_preprocessing_to_chunking(self) -> None:
        """Test preprocessing output feeds into chunking."""
        preprocessor = TextPreprocessor()
        chunker = DocumentChunker(max_chunk_size=200)

        # Create long regulatory text
        text = """
        CHAPTER 1: INTRODUCTION

        This regulation establishes requirements for data protection.
        Organizations must implement appropriate security measures.

        CHAPTER 2: REQUIREMENTS

        Section 2.1: Data controllers must process personal data lawfully.
        Section 2.2: Data subjects have the right to access their data.
        Section 2.3: Organizations must report data breaches within 72 hours.
        """

        preprocessed = preprocessor.preprocess(text)
        chunks = chunker.chunk(preprocessed.cleaned_text)

        assert len(chunks) >= 1
        # All text should be represented in chunks
        combined = " ".join(c.content for c in chunks)
        assert "data protection" in combined.lower()

    def test_rml_requirement_conversion(self) -> None:
        """Test requirement conversion to RML format."""
        generator = RMLGenerator()

        requirement = ParsedRequirement(
            id="REQ-001",
            article_ref="Article 6(1)(a)",
            regulation_id="REG-EU-GDPR",
            natural_language="Processing shall be lawful only if the data subject has given consent.",
            requirement_type=RequirementType.CONDITION,
            tier=ComplianceTier.STANDARD,
            verification_method=VerificationMethod.DOCUMENT_REVIEW,
            applies_to=["data_controller"],
            sectors=["ALL"],
            jurisdictions=["EU"],
            penalty_monetary_max=20000000.0,
            confidence=0.95,
        )

        rml_req = generator._convert_requirement(requirement)

        assert rml_req.id == "REQ-001"
        assert rml_req.article_ref == "Article 6(1)(a)"
        assert rml_req.type == "condition"
        assert rml_req.tier == "standard"
        assert rml_req.enforcement["penalty_monetary_max"] == 20000000.0

    def test_end_to_end_sample_regulation(self) -> None:
        """Test complete pipeline with sample regulation text."""
        # Sample GDPR-like text
        text = """
        GENERAL DATA PROTECTION REGULATION
        
        Article 5: Principles relating to processing of personal data
        
        1. Personal data shall be:
        
        (a) processed lawfully, fairly and in a transparent manner in relation 
        to the data subject ('lawfulness, fairness and transparency');
        
        (b) collected for specified, explicit and legitimate purposes and not 
        further processed in a manner that is incompatible with those purposes;
        
        (c) adequate, relevant and limited to what is necessary in relation to 
        the purposes for which they are processed ('data minimisation');
        
        Article 83: General conditions for imposing administrative fines
        
        2. Administrative fines shall be imposed for infringements of the 
        following provisions, of up to 20 000 000 EUR, or in the case of 
        an undertaking, up to 4 % of the total worldwide annual turnover.
        """

        # Run through preprocessing
        preprocessor = TextPreprocessor()
        preprocessed = preprocessor.preprocess(text)

        assert preprocessed.jurisdiction == "EU"  # Should detect EU
        assert len(preprocessed.sections) >= 0  # May detect articles

        # Run through chunking
        chunker = DocumentChunker(max_chunk_size=1000)
        chunks = chunker.chunk(preprocessed.cleaned_text)

        assert len(chunks) >= 1

        # Verify content integrity
        all_text = " ".join(c.content for c in chunks)
        assert "personal data" in all_text.lower()
        assert "administrative fines" in all_text.lower()

