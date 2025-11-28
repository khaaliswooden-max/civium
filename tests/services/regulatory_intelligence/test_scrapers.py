"""
Tests for Regulatory Source Scrapers
====================================

Tests for:
- Federal Register scraper
- EUR-Lex scraper
- Base scraper functionality

Version: 0.1.0
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.regulatory_intelligence.scrapers.base import (
    BaseScraper,
    DocumentType,
    ScrapedDocument,
    ScraperConfig,
    SearchResult,
)
from services.regulatory_intelligence.scrapers.federal_register import (
    FederalRegisterScraper,
    FR_TYPE_MAP,
)
from services.regulatory_intelligence.scrapers.eurlex import (
    EURLexScraper,
    EURLEX_TYPE_MAP,
)


# ============================================================================
# Scraper Config Tests
# ============================================================================


class TestScraperConfig:
    """Tests for ScraperConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ScraperConfig()

        assert config.requests_per_minute == 30
        assert config.retry_count == 3
        assert config.cache_enabled is True

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = ScraperConfig(
            requests_per_minute=10,
            retry_count=5,
            cache_enabled=False,
        )

        assert config.requests_per_minute == 10
        assert config.retry_count == 5
        assert config.cache_enabled is False


# ============================================================================
# Scraped Document Tests
# ============================================================================


class TestScrapedDocument:
    """Tests for ScrapedDocument."""

    def test_content_hash_computed(self) -> None:
        """Test content hash is computed on creation."""
        doc = ScrapedDocument(
            source="test",
            source_id="123",
            source_url="https://example.com",
            title="Test Document",
            content="Test content",
        )

        assert doc.content_hash != ""
        assert len(doc.content_hash) == 64  # SHA-256 hex

    def test_same_content_same_hash(self) -> None:
        """Test identical content produces same hash."""
        doc1 = ScrapedDocument(
            source="test",
            source_id="1",
            source_url="https://example.com/1",
            title="Doc 1",
            content="Same content",
        )

        doc2 = ScrapedDocument(
            source="test",
            source_id="2",
            source_url="https://example.com/2",
            title="Doc 2",
            content="Same content",
        )

        assert doc1.content_hash == doc2.content_hash

    def test_different_content_different_hash(self) -> None:
        """Test different content produces different hash."""
        doc1 = ScrapedDocument(
            source="test",
            source_id="1",
            source_url="https://example.com/1",
            title="Doc 1",
            content="Content A",
        )

        doc2 = ScrapedDocument(
            source="test",
            source_id="2",
            source_url="https://example.com/2",
            title="Doc 2",
            content="Content B",
        )

        assert doc1.content_hash != doc2.content_hash


# ============================================================================
# Federal Register Scraper Tests
# ============================================================================


class TestFederalRegisterScraper:
    """Tests for FederalRegisterScraper."""

    @pytest.fixture
    def scraper(self) -> FederalRegisterScraper:
        return FederalRegisterScraper()

    def test_source_name(self, scraper: FederalRegisterScraper) -> None:
        """Test source name."""
        assert scraper.source_name == "federal_register"

    def test_jurisdiction(self, scraper: FederalRegisterScraper) -> None:
        """Test jurisdiction."""
        assert scraper.jurisdiction == "US"

    def test_base_url(self, scraper: FederalRegisterScraper) -> None:
        """Test base URL."""
        assert "federalregister.gov" in scraper.base_url

    def test_clean_html_removes_scripts(self, scraper: FederalRegisterScraper) -> None:
        """Test HTML cleaning removes scripts."""
        html = "<p>Content</p><script>alert('bad')</script><p>More</p>"
        result = scraper._clean_html_content(html)

        assert "alert" not in result
        assert "Content" in result
        assert "More" in result

    def test_clean_html_converts_elements(self, scraper: FederalRegisterScraper) -> None:
        """Test HTML cleaning converts elements."""
        html = "<h1>Title</h1><p>Para 1</p><p>Para 2</p><ul><li>Item</li></ul>"
        result = scraper._clean_html_content(html)

        assert "Title" in result
        assert "Para 1" in result
        # List items should be converted
        assert "Item" in result

    @pytest.mark.asyncio
    async def test_search_with_query(self, scraper: FederalRegisterScraper) -> None:
        """Test search with mock response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "document_number": "2024-12345",
                    "title": "Test Rule",
                    "type": "RULE",
                    "publication_date": "2024-01-15",
                    "html_url": "https://federalregister.gov/d/2024-12345",
                    "abstract": "This is a test rule.",
                    "agencies": [{"name": "Test Agency"}],
                },
            ],
        }

        with patch.object(scraper, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            results = await scraper.search("test query", limit=10)

            assert len(results) == 1
            assert results[0].source_id == "2024-12345"
            assert results[0].title == "Test Rule"
            assert results[0].document_type == DocumentType.RULE

    @pytest.mark.asyncio
    async def test_search_with_date_range(self, scraper: FederalRegisterScraper) -> None:
        """Test search with date range."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}

        with patch.object(scraper, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            await scraper.search(
                "test",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
            )

            # Verify date params were passed
            call_kwargs = mock_request.call_args.kwargs
            assert "params" in call_kwargs
            params = call_kwargs["params"]
            assert "conditions[publication_date][gte]" in params
            assert "conditions[publication_date][lte]" in params

    @pytest.mark.asyncio
    async def test_get_document(self, scraper: FederalRegisterScraper) -> None:
        """Test getting a specific document."""
        mock_meta_response = MagicMock()
        mock_meta_response.json.return_value = {
            "document_number": "2024-12345",
            "title": "Final Rule: Test Requirements",
            "type": "RULE",
            "publication_date": "2024-01-15",
            "effective_on": "2024-03-01",
            "html_url": "https://federalregister.gov/d/2024-12345",
            "body_html_url": "https://federalregister.gov/d/2024-12345/content.html",
            "agencies": [{"name": "Securities and Exchange Commission"}],
            "cfr_references": [{"title": "17", "parts": ["240", "249"]}],
            "abstract": "This rule establishes new requirements.",
            "docket_ids": ["SEC-2024-001"],
        }

        mock_content_response = MagicMock()
        mock_content_response.text = "<html><body><p>Rule content here.</p></body></html>"

        with patch.object(scraper, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [mock_meta_response, mock_content_response]

            doc = await scraper.get_document("2024-12345")

            assert doc.source_id == "2024-12345"
            assert doc.title == "Final Rule: Test Requirements"
            assert doc.document_type == DocumentType.RULE
            assert doc.publication_date == date(2024, 1, 15)
            assert doc.effective_date == date(2024, 3, 1)
            assert "Securities and Exchange Commission" in doc.agencies
            assert len(doc.cfr_references) == 2


# ============================================================================
# EUR-Lex Scraper Tests
# ============================================================================


class TestEURLexScraper:
    """Tests for EURLexScraper."""

    @pytest.fixture
    def scraper(self) -> EURLexScraper:
        return EURLexScraper()

    def test_source_name(self, scraper: EURLexScraper) -> None:
        """Test source name."""
        assert scraper.source_name == "eurlex"

    def test_jurisdiction(self, scraper: EURLexScraper) -> None:
        """Test jurisdiction."""
        assert scraper.jurisdiction == "EU"

    def test_base_url(self, scraper: EURLexScraper) -> None:
        """Test base URL."""
        assert "eur-lex.europa.eu" in scraper.base_url

    def test_detect_regulation_type(self, scraper: EURLexScraper) -> None:
        """Test regulation type detection from CELEX."""
        # Regulation (R)
        assert scraper._detect_document_type("32016R0679") == DocumentType.REGULATION
        # Directive (L)
        assert scraper._detect_document_type("32014L0065") == DocumentType.DIRECTIVE

    def test_clean_html_removes_navigation(self, scraper: EURLexScraper) -> None:
        """Test HTML cleaning removes navigation."""
        html = "<nav>Menu</nav><main>Content</main><footer>Footer</footer>"
        result = scraper._clean_html_content(html)

        assert "Menu" not in result
        assert "Footer" not in result
        assert "Content" in result

    def test_extract_title_from_title_tag(self, scraper: EURLexScraper) -> None:
        """Test title extraction from title tag."""
        html = "<html><head><title>EUR-Lex - Test Regulation</title></head></html>"
        title = scraper._extract_title(html)

        assert "Test Regulation" in (title or "")

    def test_extract_title_from_h1(self, scraper: EURLexScraper) -> None:
        """Test title extraction from h1 tag."""
        html = "<html><body><h1>Regulation Title</h1></body></html>"
        title = scraper._extract_title(html)

        assert title == "Regulation Title"

    @pytest.mark.asyncio
    async def test_get_regulation(self, scraper: EURLexScraper) -> None:
        """Test getting regulation by year and number."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
        <head><title>GDPR - Regulation (EU) 2016/679</title></head>
        <body>
            <main>
                <h1>General Data Protection Regulation</h1>
                <p>Article 1: Subject matter and objectives</p>
            </main>
        </body>
        </html>
        """

        with patch.object(scraper, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            doc = await scraper.get_regulation(2016, 679)

            # Should construct correct CELEX
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert "32016R0679" in str(call_args)

            assert doc.document_type == DocumentType.REGULATION

    @pytest.mark.asyncio
    async def test_get_directive(self, scraper: EURLexScraper) -> None:
        """Test getting directive by year and number."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
        <head><title>MiFID II - Directive 2014/65/EU</title></head>
        <body><main><p>Directive content</p></main></body>
        </html>
        """

        with patch.object(scraper, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            doc = await scraper.get_directive(2014, 65)

            # Should construct correct CELEX
            call_args = mock_request.call_args
            assert "32014L0065" in str(call_args)

            assert doc.document_type == DocumentType.DIRECTIVE


# ============================================================================
# Base Scraper Tests
# ============================================================================


class TestBaseScraper:
    """Tests for BaseScraper base class."""

    @pytest.mark.asyncio
    async def test_check_for_updates_no_change(self) -> None:
        """Test update check when content unchanged."""
        scraper = FederalRegisterScraper()

        mock_doc = ScrapedDocument(
            source="federal_register",
            source_id="2024-12345",
            source_url="https://example.com",
            title="Test",
            content="Test content",
        )

        with patch.object(scraper, "get_document", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_doc

            has_changed, new_hash = await scraper.check_for_updates(
                "2024-12345",
                mock_doc.content_hash,  # Same hash
            )

            assert has_changed is False
            assert new_hash == mock_doc.content_hash

    @pytest.mark.asyncio
    async def test_check_for_updates_with_change(self) -> None:
        """Test update check when content changed."""
        scraper = FederalRegisterScraper()

        mock_doc = ScrapedDocument(
            source="federal_register",
            source_id="2024-12345",
            source_url="https://example.com",
            title="Test",
            content="New content",  # Different content
        )

        old_hash = "different_hash_value_here"

        with patch.object(scraper, "get_document", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_doc

            has_changed, new_hash = await scraper.check_for_updates(
                "2024-12345",
                old_hash,
            )

            assert has_changed is True
            assert new_hash == mock_doc.content_hash


# ============================================================================
# Document Type Mapping Tests
# ============================================================================


class TestDocumentTypeMappings:
    """Tests for document type mappings."""

    def test_federal_register_type_map(self) -> None:
        """Test Federal Register type mapping."""
        assert FR_TYPE_MAP["RULE"] == DocumentType.RULE
        assert FR_TYPE_MAP["PRORULE"] == DocumentType.PROPOSED_RULE
        assert FR_TYPE_MAP["NOTICE"] == DocumentType.NOTICE
        assert FR_TYPE_MAP["PRESDOCU"] == DocumentType.EXECUTIVE_ORDER

    def test_eurlex_type_map(self) -> None:
        """Test EUR-Lex type mapping."""
        assert EURLEX_TYPE_MAP["REG"] == DocumentType.REGULATION
        assert EURLEX_TYPE_MAP["DIR"] == DocumentType.DIRECTIVE

