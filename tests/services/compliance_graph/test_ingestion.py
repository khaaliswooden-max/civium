"""
Tests for Graph Ingestion
=========================

Tests for RML to Neo4j ingestion.

Version: 0.1.0
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.compliance_graph.ingestion.rml_ingester import (
    RMLIngester,
    IngestionOptions,
    IngestionResult,
)
from services.compliance_graph.ingestion.batch_ingester import (
    BatchIngester,
    BatchResult,
)


# =============================================================================
# Sample RML Data
# =============================================================================


SAMPLE_RML = {
    "id": "REG-US-TEST001",
    "name": "Test Regulation",
    "short_name": "TestReg",
    "jurisdiction": "US",
    "jurisdictions": ["US"],
    "sectors": ["FINANCE", "TECH"],
    "governance_layer": 3,
    "source": {
        "url": "https://example.com/reg",
        "hash": "abc123",
    },
    "effective_date": "2024-01-01",
    "requirements": [
        {
            "id": "REQ-TEST-001",
            "article_ref": "Section 1.1",
            "text": "Organizations must implement security controls.",
            "tier": "standard",
            "verification_method": "document_review",
            "scope": {
                "jurisdictions": ["US"],
                "sectors": ["FINANCE"],
                "entities": ["corporation"],
            },
            "temporal": {
                "effective_date": "2024-01-01",
            },
            "enforcement": {
                "penalty_monetary_max": 1000000,
            },
            "references": [],
            "metadata": {
                "confidence": 0.9,
            },
        },
        {
            "id": "REQ-TEST-002",
            "article_ref": "Section 1.2",
            "text": "Security controls must be audited annually.",
            "tier": "advanced",
            "verification_method": "on_site_audit",
            "scope": {
                "jurisdictions": ["US"],
                "sectors": ["FINANCE"],
            },
            "references": [
                {"type": "depends_on", "target": "REQ-TEST-001"},
            ],
        },
    ],
}


# =============================================================================
# Ingestion Options Tests
# =============================================================================


class TestIngestionOptions:
    """Tests for IngestionOptions."""

    def test_default_options(self) -> None:
        """Test default option values."""
        opts = IngestionOptions()

        assert opts.create_regulations is True
        assert opts.create_requirements is True
        assert opts.create_jurisdictions is True
        assert opts.create_sectors is True
        assert opts.upsert is True
        assert opts.batch_size == 100

    def test_custom_options(self) -> None:
        """Test custom option values."""
        opts = IngestionOptions(
            create_regulations=False,
            upsert=False,
            batch_size=50,
        )

        assert opts.create_regulations is False
        assert opts.upsert is False
        assert opts.batch_size == 50


# =============================================================================
# Ingestion Result Tests
# =============================================================================


class TestIngestionResult:
    """Tests for IngestionResult."""

    def test_empty_result(self) -> None:
        """Test empty result."""
        result = IngestionResult()

        assert result.success is True
        assert result.total_nodes_created == 0

    def test_result_with_counts(self) -> None:
        """Test result with counts."""
        result = IngestionResult(
            regulations_created=1,
            requirements_created=5,
            jurisdictions_created=2,
            relationships_created=10,
        )

        assert result.total_nodes_created == 8
        assert result.success is True

    def test_result_with_errors(self) -> None:
        """Test result with errors."""
        result = IngestionResult(
            errors=[{"type": "test", "error": "Test error"}],
        )

        assert result.success is False


# =============================================================================
# RML Ingester Tests
# =============================================================================


class TestRMLIngester:
    """Tests for RMLIngester."""

    @pytest.fixture
    def ingester(self) -> RMLIngester:
        return RMLIngester()

    def test_extract_jurisdictions(self, ingester: RMLIngester) -> None:
        """Test jurisdiction extraction from RML."""
        jurisdictions = ingester._extract_jurisdictions(SAMPLE_RML)

        assert "US" in jurisdictions
        assert len(jurisdictions) >= 1

    def test_extract_sectors(self, ingester: RMLIngester) -> None:
        """Test sector extraction from RML."""
        sectors = ingester._extract_sectors(SAMPLE_RML)

        assert "FINANCE" in sectors
        assert "TECH" in sectors

    def test_extract_jurisdictions_from_requirements(self, ingester: RMLIngester) -> None:
        """Test jurisdictions are extracted from requirements."""
        rml = {
            "id": "REG-001",
            "name": "Test",
            "jurisdiction": "US",
            "requirements": [
                {
                    "id": "REQ-001",
                    "scope": {"jurisdictions": ["EU", "UK"]},
                },
            ],
        }

        jurisdictions = ingester._extract_jurisdictions(rml)

        assert "US" in jurisdictions
        assert "EU" in jurisdictions
        assert "UK" in jurisdictions

    @pytest.mark.asyncio
    async def test_ingest_creates_result(self, ingester: RMLIngester) -> None:
        """Test ingestion returns result."""
        with patch("services.compliance_graph.ingestion.rml_ingester.Neo4jClient") as mock_client:
            mock_client.run_query = AsyncMock(return_value=[{"created": True}])
            mock_client.run_write_query = AsyncMock(return_value={})

            result = await ingester.ingest(SAMPLE_RML)

            assert isinstance(result, IngestionResult)
            assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_ingest_handles_errors(self, ingester: RMLIngester) -> None:
        """Test ingestion handles errors gracefully."""
        with patch("services.compliance_graph.ingestion.rml_ingester.Neo4jClient") as mock_client:
            mock_client.run_query = AsyncMock(side_effect=Exception("Connection failed"))

            result = await ingester.ingest(SAMPLE_RML)

            assert result.success is False
            assert len(result.errors) > 0


class TestRMLIngesterWithOptions:
    """Tests for RMLIngester with different options."""

    @pytest.mark.asyncio
    async def test_skip_regulations(self) -> None:
        """Test skipping regulation creation."""
        opts = IngestionOptions(create_regulations=False)
        ingester = RMLIngester(opts)

        with patch("services.compliance_graph.ingestion.rml_ingester.Neo4jClient") as mock_client:
            mock_client.run_query = AsyncMock(return_value=[{"created": True}])
            mock_client.run_write_query = AsyncMock(return_value={})

            result = await ingester.ingest(SAMPLE_RML)

            assert result.regulations_created == 0

    @pytest.mark.asyncio
    async def test_skip_jurisdictions(self) -> None:
        """Test skipping jurisdiction creation."""
        opts = IngestionOptions(create_jurisdictions=False)
        ingester = RMLIngester(opts)

        with patch("services.compliance_graph.ingestion.rml_ingester.Neo4jClient") as mock_client:
            mock_client.run_query = AsyncMock(return_value=[{"created": True}])
            mock_client.run_write_query = AsyncMock(return_value={})

            result = await ingester.ingest(SAMPLE_RML)

            assert result.jurisdictions_created == 0


# =============================================================================
# Batch Ingester Tests
# =============================================================================


class TestBatchIngester:
    """Tests for BatchIngester."""

    @pytest.fixture
    def batch_ingester(self) -> BatchIngester:
        return BatchIngester(max_concurrent=2)

    def test_init_with_concurrency(self) -> None:
        """Test initialization with concurrency limit."""
        ingester = BatchIngester(max_concurrent=5)
        assert ingester.max_concurrent == 5

    @pytest.mark.asyncio
    async def test_batch_ingest_empty_list(self, batch_ingester: BatchIngester) -> None:
        """Test batch ingestion with empty list."""
        result = await batch_ingester.ingest_batch([])

        assert result.documents_processed == 0
        assert result.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_batch_ingest_single_document(self, batch_ingester: BatchIngester) -> None:
        """Test batch ingestion with single document."""
        with patch.object(RMLIngester, "ingest", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = IngestionResult(
                regulations_created=1,
                requirements_created=2,
            )

            result = await batch_ingester.ingest_batch([SAMPLE_RML])

            assert result.documents_processed == 1
            assert result.documents_succeeded == 1
            assert result.total_regulations == 1
            assert result.total_requirements == 2

    @pytest.mark.asyncio
    async def test_batch_ingest_multiple_documents(self, batch_ingester: BatchIngester) -> None:
        """Test batch ingestion with multiple documents."""
        documents = [
            {"id": "REG-001", "name": "Reg 1", "requirements": []},
            {"id": "REG-002", "name": "Reg 2", "requirements": []},
            {"id": "REG-003", "name": "Reg 3", "requirements": []},
        ]

        with patch.object(RMLIngester, "ingest", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = IngestionResult(regulations_created=1)

            result = await batch_ingester.ingest_batch(documents)

            assert result.documents_processed == 3
            assert result.documents_succeeded == 3
            assert mock_ingest.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_ingest_handles_failures(self, batch_ingester: BatchIngester) -> None:
        """Test batch ingestion handles individual failures."""
        documents = [
            {"id": "REG-001", "name": "Reg 1", "requirements": []},
            {"id": "REG-002", "name": "Reg 2", "requirements": []},
        ]

        call_count = 0

        async def mock_ingest_with_failure(*args: object, **kwargs: object) -> IngestionResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return IngestionResult(regulations_created=1)
            else:
                return IngestionResult(errors=[{"error": "Test failure"}])

        with patch.object(RMLIngester, "ingest", side_effect=mock_ingest_with_failure):
            result = await batch_ingester.ingest_batch(documents)

            assert result.documents_processed == 2
            assert result.documents_succeeded == 1
            assert result.documents_failed == 1


class TestBatchResult:
    """Tests for BatchResult."""

    def test_success_rate_calculation(self) -> None:
        """Test success rate calculation."""
        result = BatchResult(
            documents_processed=10,
            documents_succeeded=8,
            documents_failed=2,
        )

        assert result.success_rate == 0.8

    def test_success_rate_zero_documents(self) -> None:
        """Test success rate with zero documents."""
        result = BatchResult()

        assert result.success_rate == 0.0

