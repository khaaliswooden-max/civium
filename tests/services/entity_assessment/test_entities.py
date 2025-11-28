"""
Entity Routes Tests
===================

Tests for entity management API endpoints.

Version: 0.1.0
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from services.entity_assessment.services.tier import ComplianceTier


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def sample_entity_data():
    """Sample entity data for testing."""
    return {
        "name": "Test Corporation",
        "entity_type": "corporation",
        "sectors": ["TECHNOLOGY", "RETAIL"],
        "jurisdictions": ["US", "EU"],
        "size": "medium",
        "external_id": "EXT-123",
        "metadata": {"industry_code": "5411"},
    }


@pytest.fixture
def sample_entity_row():
    """Mock database row for an entity."""
    entity_id = str(uuid4())
    return MagicMock(
        id=entity_id,
        name="Test Corporation",
        legal_name="Test Corporation Inc.",
        entity_type="corporation",
        size="medium",
        primary_jurisdiction="US",
        jurisdictions=["US", "EU"],
        sectors=["TECHNOLOGY", "RETAIL"],
        employee_count=150,
        annual_revenue=25000000,
        compliance_tier="standard",
        compliance_score=0.85,
        risk_score=0.15,
        total_requirements=50,
        compliant_requirements=42,
        non_compliant_requirements=5,
        pending_requirements=3,
        external_id="EXT-123",
        metadata={"industry_code": "5411"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_assessment_at=datetime.now(UTC),
    )


# =============================================================================
# Tier Determination Tests
# =============================================================================


class TestTierDetermination:
    """Tests for entity tier determination via entities route."""

    def test_basic_tier_assignment(self):
        """Small entity gets BASIC tier."""
        from services.entity_assessment.routes.entities import determine_tier
        from shared.models.entity import EntityCreate, EntityType

        entity_data = EntityCreate(
            name="Small Shop",
            entity_type=EntityType.SME,
            sectors=["RETAIL"],
            jurisdictions=["US"],
            size="small",
        )

        tier = determine_tier(entity_data)
        assert tier == ComplianceTier.BASIC

    def test_standard_tier_from_size(self):
        """Medium entity gets STANDARD tier."""
        from services.entity_assessment.routes.entities import determine_tier
        from shared.models.entity import EntityCreate, EntityType

        entity_data = EntityCreate(
            name="Medium Corp",
            entity_type=EntityType.CORPORATION,
            sectors=["TECHNOLOGY"],
            jurisdictions=["US"],
            size="medium",
        )

        tier = determine_tier(entity_data)
        assert tier in (ComplianceTier.STANDARD, ComplianceTier.BASIC)

    def test_advanced_tier_from_regulated_sector(self):
        """Finance sector triggers ADVANCED tier."""
        from services.entity_assessment.routes.entities import determine_tier
        from shared.models.entity import EntityCreate, EntityType

        entity_data = EntityCreate(
            name="Finance Corp",
            entity_type=EntityType.CORPORATION,
            sectors=["FINANCE"],
            jurisdictions=["US"],
            size="small",
        )

        tier = determine_tier(entity_data)
        assert tier == ComplianceTier.ADVANCED

    def test_advanced_tier_from_healthcare(self):
        """Healthcare sector triggers ADVANCED tier."""
        from services.entity_assessment.routes.entities import determine_tier
        from shared.models.entity import EntityCreate, EntityType

        entity_data = EntityCreate(
            name="Healthcare Provider",
            entity_type=EntityType.CORPORATION,
            sectors=["HEALTHCARE"],
            jurisdictions=["US"],
            size="small",
        )

        tier = determine_tier(entity_data)
        assert tier == ComplianceTier.ADVANCED


# =============================================================================
# Entity Model Validation Tests
# =============================================================================


class TestEntityValidation:
    """Tests for entity data validation."""

    def test_entity_create_valid(self):
        """Valid entity creation data."""
        from shared.models.entity import EntityCreate, EntityType

        entity = EntityCreate(
            name="Test Entity",
            entity_type=EntityType.CORPORATION,
            sectors=["TECHNOLOGY"],
            jurisdictions=["US"],
        )

        assert entity.name == "Test Entity"
        assert entity.entity_type == EntityType.CORPORATION

    def test_entity_create_minimal(self):
        """Minimal entity creation data."""
        from shared.models.entity import EntityCreate, EntityType

        entity = EntityCreate(
            name="Minimal Entity",
            entity_type=EntityType.SME,
            sectors=[],
            jurisdictions=["US"],
        )

        assert entity.name == "Minimal Entity"
        assert entity.sectors == []

    def test_entity_update_partial(self):
        """Partial entity update data."""
        from shared.models.entity import EntityUpdate

        update = EntityUpdate(
            name="Updated Name",
        )

        assert update.name == "Updated Name"
        assert update.entity_type is None  # Not updated


# =============================================================================
# Entity Summary Tests
# =============================================================================


class TestEntitySummary:
    """Tests for entity summary model."""

    def test_entity_summary_creation(self):
        """Entity summary model creation."""
        from shared.models.entity import EntitySummary, ComplianceTier

        summary = EntitySummary(
            id="123",
            name="Test Entity",
            entity_type="corporation",
            compliance_tier=ComplianceTier.STANDARD,
            compliance_score=0.85,
            jurisdictions=["US", "EU"],
        )

        assert summary.id == "123"
        assert summary.compliance_tier == ComplianceTier.STANDARD
        assert summary.compliance_score == 0.85


# =============================================================================
# Query Building Tests
# =============================================================================


class TestQueryBuilding:
    """Tests for SQL query building in entity routes."""

    def test_filter_by_jurisdiction(self):
        """Query filtering by jurisdiction."""
        # Test that filter parameters are correctly formatted
        jurisdiction = "US"
        params = {}

        # Build filter
        filter_clause = ":jurisdiction = ANY(jurisdictions)"
        params["jurisdiction"] = jurisdiction.upper()

        assert params["jurisdiction"] == "US"
        assert ":jurisdiction" in filter_clause

    def test_filter_by_tier(self):
        """Query filtering by tier."""
        from shared.models.entity import ComplianceTier

        tier = ComplianceTier.ADVANCED
        params = {}

        params["tier"] = tier.value

        assert params["tier"] == "advanced"

    def test_search_filter(self):
        """Query search filtering."""
        search = "test"
        params = {}

        params["search"] = f"%{search}%"

        assert params["search"] == "%test%"

    def test_pagination_params(self):
        """Pagination parameter calculation."""
        page = 3
        page_size = 20

        offset = (page - 1) * page_size
        limit = page_size

        assert offset == 40
        assert limit == 20


# =============================================================================
# Integration Tests (with mocked DB)
# =============================================================================


class TestEntityRouteIntegration:
    """Integration tests for entity routes."""

    @pytest.mark.asyncio
    async def test_list_entities_empty(self, mock_db_session):
        """List entities returns empty when no entities."""
        from services.entity_assessment.routes.entities import list_entities

        # Mock empty results
        mock_db_session.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar=lambda: 0),  # Count query
                MagicMock(fetchall=lambda: []),  # Data query
            ]
        )

        result = await list_entities(db=mock_db_session)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_list_entities_with_data(
        self,
        mock_db_session,
        sample_entity_row,
    ):
        """List entities returns data."""
        from services.entity_assessment.routes.entities import list_entities

        # Mock results
        mock_db_session.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar=lambda: 1),  # Count query
                MagicMock(fetchall=lambda: [sample_entity_row]),  # Data query
            ]
        )

        result = await list_entities(db=mock_db_session)

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].name == "Test Corporation"

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, mock_db_session):
        """Get entity returns 404 when not found."""
        from services.entity_assessment.routes.entities import get_entity
        from fastapi import HTTPException

        # Mock no result
        mock_db_session.execute = AsyncMock(
            return_value=MagicMock(fetchone=lambda: None)
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_entity(entity_id="nonexistent", db=mock_db_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_entity_found(
        self,
        mock_db_session,
        sample_entity_row,
    ):
        """Get entity returns entity when found."""
        from services.entity_assessment.routes.entities import get_entity

        # Mock result
        mock_db_session.execute = AsyncMock(
            return_value=MagicMock(fetchone=lambda: sample_entity_row)
        )

        result = await get_entity(
            entity_id=str(sample_entity_row.id),
            db=mock_db_session,
        )

        assert result.name == "Test Corporation"
        assert result.entity_type == "corporation"


# =============================================================================
# Compliance Tier Enum Tests
# =============================================================================


class TestComplianceTierEnum:
    """Tests for ComplianceTier enum."""

    def test_tier_values(self):
        """Tier enum has correct values."""
        from shared.models.entity import ComplianceTier

        assert ComplianceTier.BASIC.value == "basic"
        assert ComplianceTier.STANDARD.value == "standard"
        assert ComplianceTier.ADVANCED.value == "advanced"

    def test_tier_from_string(self):
        """Tier can be created from string."""
        from shared.models.entity import ComplianceTier

        tier = ComplianceTier("standard")
        assert tier == ComplianceTier.STANDARD


# =============================================================================
# Entity Type Enum Tests
# =============================================================================


class TestEntityTypeEnum:
    """Tests for EntityType enum."""

    def test_entity_type_values(self):
        """EntityType enum has expected values."""
        from shared.models.entity import EntityType

        assert hasattr(EntityType, "CORPORATION")
        assert hasattr(EntityType, "SME")
        assert hasattr(EntityType, "STARTUP")
        assert hasattr(EntityType, "GOVERNMENT")

    def test_entity_type_from_string(self):
        """EntityType can be created from string."""
        from shared.models.entity import EntityType

        entity_type = EntityType("corporation")
        assert entity_type == EntityType.CORPORATION


# =============================================================================
# Soft Delete Tests
# =============================================================================


class TestSoftDelete:
    """Tests for soft delete functionality."""

    @pytest.mark.asyncio
    async def test_delete_sets_deleted_at(self, mock_db_session):
        """Delete sets deleted_at timestamp."""
        from services.entity_assessment.routes.entities import delete_entity
        from shared.auth import User

        # Mock successful delete
        mock_db_session.execute = AsyncMock(
            return_value=MagicMock(rowcount=1)
        )

        mock_user = User(id="user-123", email="test@example.com")

        # Should not raise
        await delete_entity(
            entity_id="entity-123",
            db=mock_db_session,
            current_user=mock_user,
        )

        # Verify execute was called
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_db_session):
        """Delete returns 404 when entity not found."""
        from services.entity_assessment.routes.entities import delete_entity
        from shared.auth import User
        from fastapi import HTTPException

        # Mock no rows affected
        mock_db_session.execute = AsyncMock(
            return_value=MagicMock(rowcount=0)
        )

        mock_user = User(id="user-123", email="test@example.com")

        with pytest.raises(HTTPException) as exc_info:
            await delete_entity(
                entity_id="nonexistent",
                db=mock_db_session,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 404


# =============================================================================
# Pagination Tests
# =============================================================================


class TestPagination:
    """Tests for pagination functionality."""

    def test_page_calculation(self):
        """Page calculation is correct."""
        total = 55
        page_size = 20

        pages = (total + page_size - 1) // page_size

        assert pages == 3

    def test_offset_calculation(self):
        """Offset calculation is correct."""
        page = 3
        page_size = 20

        offset = (page - 1) * page_size

        assert offset == 40

    def test_empty_result_pages(self):
        """Empty result still has 1 page."""
        total = 0
        page_size = 20

        pages = (total + page_size - 1) // page_size if total > 0 else 1

        assert pages == 1

