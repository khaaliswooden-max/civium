"""Tests for threat assessment engine."""

import pytest
from datetime import datetime

from services.visitor.ml.threat_assessment.engine import (
    ThreatAssessmentEngine,
    ThreatAssessmentConfig,
    ThreatLevel,
    WatchlistType,
)


@pytest.fixture
def engine() -> ThreatAssessmentEngine:
    """Create threat assessment engine for testing."""
    config = ThreatAssessmentConfig()
    return ThreatAssessmentEngine(config)


@pytest.fixture
def sample_visitor_data() -> dict:
    """Sample visitor data for testing."""
    return {
        "id": "VIS-TEST001",
        "full_name": "John Doe",
        "date_of_birth": "1985-03-15",
        "purpose": "Business meeting",
        "visits_last_30_days": 2,
        "previous_denials": 0,
    }


@pytest.fixture
def sample_id_document() -> bytes:
    """Sample ID document bytes."""
    return b"FAKE_ID_DOCUMENT_IMAGE_DATA_FOR_TESTING"


@pytest.fixture
def sample_selfie() -> bytes:
    """Sample selfie bytes."""
    return b"FAKE_SELFIE_IMAGE_DATA_FOR_TESTING"


class TestThreatAssessmentEngine:
    """Tests for ThreatAssessmentEngine."""

    @pytest.mark.asyncio
    async def test_screen_visitor_clear(
        self,
        engine: ThreatAssessmentEngine,
        sample_visitor_data: dict,
        sample_id_document: bytes,
        sample_selfie: bytes,
    ) -> None:
        """Test screening a normal visitor returns CLEAR."""
        async with engine:
            result = await engine.screen_visitor(
                sample_visitor_data,
                sample_id_document,
                sample_selfie,
            )

        assert result.visitor_id == "VIS-TEST001"
        assert result.threat_level == ThreatLevel.CLEAR
        assert result.confidence > 0.5
        assert result.recommended_action == "Approved for entry"
        assert not result.requires_escort

    @pytest.mark.asyncio
    async def test_screen_visitor_with_denials(
        self,
        engine: ThreatAssessmentEngine,
        sample_visitor_data: dict,
        sample_id_document: bytes,
        sample_selfie: bytes,
    ) -> None:
        """Test visitor with previous denials gets escalated."""
        sample_visitor_data["previous_denials"] = 2

        async with engine:
            result = await engine.screen_visitor(
                sample_visitor_data,
                sample_id_document,
                sample_selfie,
            )

        assert result.threat_level in [ThreatLevel.REVIEW, ThreatLevel.ESCALATE, ThreatLevel.DENY]
        assert len(result.behavioral_flags) > 0
        assert any(f["type"] == "previous_denial" for f in result.behavioral_flags)

    @pytest.mark.asyncio
    async def test_screen_visitor_high_frequency(
        self,
        engine: ThreatAssessmentEngine,
        sample_visitor_data: dict,
        sample_id_document: bytes,
        sample_selfie: bytes,
    ) -> None:
        """Test visitor with high visit frequency gets flagged."""
        sample_visitor_data["visits_last_30_days"] = 15

        async with engine:
            result = await engine.screen_visitor(
                sample_visitor_data,
                sample_id_document,
                sample_selfie,
            )

        assert any(f["type"] == "high_frequency" for f in result.behavioral_flags)

    def test_analyze_behavior_empty(self, engine: ThreatAssessmentEngine) -> None:
        """Test behavior analysis with no flags."""
        visitor_data = {"id": "VIS-001", "full_name": "Test User"}
        flags = engine._analyze_behavior(visitor_data)
        assert flags == []

    def test_analyze_behavior_all_flags(self, engine: ThreatAssessmentEngine) -> None:
        """Test behavior analysis with all possible flags."""
        visitor_data = {
            "id": "VIS-001",
            "full_name": "Test User",
            "visits_last_30_days": 15,
            "previous_denials": 3,
            "credentials_expired": True,
        }
        flags = engine._analyze_behavior(visitor_data)
        assert len(flags) == 3


class TestWatchlistScreening:
    """Tests for watchlist screening functionality."""

    @pytest.mark.asyncio
    async def test_screen_watchlists_no_hits(
        self,
        engine: ThreatAssessmentEngine,
    ) -> None:
        """Test watchlist screening with no matches."""
        async with engine:
            results = await engine._screen_watchlists(
                name="John Smith",
                dob="1990-01-01",
                id_number="ABC123",
                nationality="US",
            )

        assert WatchlistType.SDN in results
        assert results[WatchlistType.SDN] is not None
        assert results[WatchlistType.SDN]["highest_score"] == 0

