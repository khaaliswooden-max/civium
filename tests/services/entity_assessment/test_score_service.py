"""
Score Service Tests
===================

Tests for the compliance score calculation service.

Version: 0.1.0
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from services.entity_assessment.services.score import (
    ScoreService,
    ScoreWeights,
    ScoreBreakdown,
    ScoreResult,
    ScoreType,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def score_service() -> ScoreService:
    """Get a score service with default weights."""
    return ScoreService()


@pytest.fixture
def custom_score_service() -> ScoreService:
    """Get a score service with custom weights."""
    weights = ScoreWeights(
        tier_weights={
            "basic": 1.0,
            "standard": 2.0,  # Higher weight
            "advanced": 3.0,
        },
        status_weights={
            "compliant": 1.0,
            "partial": 0.7,  # Different weight
            "non_compliant": 0.0,
            "pending": 0.0,
            "not_applicable": None,
        },
    )
    return ScoreService(weights)


@pytest.fixture
def sample_assessment_items() -> list[dict]:
    """Sample assessment items for testing."""
    return [
        {
            "requirement_id": "req-001",
            "status": "compliant",
            "requirement_tier": "basic",
            "regulation_id": "reg-001",
            "risk_impact": "low",
            "score": 1.0,
        },
        {
            "requirement_id": "req-002",
            "status": "compliant",
            "requirement_tier": "basic",
            "regulation_id": "reg-001",
            "risk_impact": "low",
            "score": 1.0,
        },
        {
            "requirement_id": "req-003",
            "status": "non_compliant",
            "requirement_tier": "standard",
            "regulation_id": "reg-002",
            "risk_impact": "medium",
            "score": 0.0,
        },
        {
            "requirement_id": "req-004",
            "status": "partial",
            "requirement_tier": "standard",
            "regulation_id": "reg-002",
            "risk_impact": "medium",
            "score": 0.5,
        },
        {
            "requirement_id": "req-005",
            "status": "not_applicable",
            "requirement_tier": "advanced",
            "regulation_id": "reg-003",
            "risk_impact": "high",
            "score": None,
        },
    ]


@pytest.fixture
def all_compliant_items() -> list[dict]:
    """All compliant assessment items."""
    return [
        {
            "requirement_id": f"req-{i:03d}",
            "status": "compliant",
            "requirement_tier": "basic",
            "regulation_id": "reg-001",
            "risk_impact": "low",
            "score": 1.0,
        }
        for i in range(10)
    ]


@pytest.fixture
def mixed_tier_items() -> list[dict]:
    """Items with different tiers."""
    return [
        {"requirement_id": "basic-1", "status": "compliant", "requirement_tier": "basic", "risk_impact": "low"},
        {"requirement_id": "basic-2", "status": "compliant", "requirement_tier": "basic", "risk_impact": "low"},
        {"requirement_id": "standard-1", "status": "compliant", "requirement_tier": "standard", "risk_impact": "medium"},
        {"requirement_id": "standard-2", "status": "non_compliant", "requirement_tier": "standard", "risk_impact": "medium"},
        {"requirement_id": "advanced-1", "status": "non_compliant", "requirement_tier": "advanced", "risk_impact": "high"},
    ]


# =============================================================================
# Breakdown Calculation Tests
# =============================================================================


class TestScoreBreakdown:
    """Tests for score breakdown calculation."""

    def test_breakdown_counts_correct(
        self,
        score_service: ScoreService,
        sample_assessment_items: list[dict],
    ) -> None:
        """Breakdown correctly counts items by status."""
        breakdown = score_service._calculate_breakdown(sample_assessment_items)

        assert breakdown.compliant == 2
        assert breakdown.non_compliant == 1
        assert breakdown.partial == 1
        assert breakdown.not_applicable == 1
        # N/A excluded from total
        assert breakdown.total_requirements == 4

    def test_breakdown_by_tier(
        self,
        score_service: ScoreService,
        sample_assessment_items: list[dict],
    ) -> None:
        """Breakdown correctly groups by tier."""
        breakdown = score_service._calculate_breakdown(sample_assessment_items)

        assert "basic" in breakdown.by_tier
        assert breakdown.by_tier["basic"]["total"] == 2
        assert breakdown.by_tier["basic"]["compliant"] == 2

        assert "standard" in breakdown.by_tier
        assert breakdown.by_tier["standard"]["total"] == 2
        assert breakdown.by_tier["standard"]["compliant"] == 0

    def test_breakdown_by_regulation(
        self,
        score_service: ScoreService,
        sample_assessment_items: list[dict],
    ) -> None:
        """Breakdown correctly groups by regulation."""
        breakdown = score_service._calculate_breakdown(sample_assessment_items)

        assert "reg-001" in breakdown.by_regulation
        # Both items in reg-001 are compliant
        assert breakdown.by_regulation["reg-001"] == 1.0

        assert "reg-002" in breakdown.by_regulation
        # 0 of 2 items compliant in reg-002
        assert breakdown.by_regulation["reg-002"] == 0.0


# =============================================================================
# Simple Score Tests
# =============================================================================


class TestSimpleScore:
    """Tests for simple score calculation."""

    def test_perfect_score(
        self,
        score_service: ScoreService,
        all_compliant_items: list[dict],
    ) -> None:
        """All compliant items result in perfect score."""
        breakdown = score_service._calculate_breakdown(all_compliant_items)
        score = score_service._calculate_simple_score(breakdown)

        assert score == 1.0

    def test_zero_score(self, score_service: ScoreService) -> None:
        """All non-compliant items result in zero score."""
        items = [
            {"requirement_id": "req-1", "status": "non_compliant", "requirement_tier": "basic", "risk_impact": "low"},
            {"requirement_id": "req-2", "status": "non_compliant", "requirement_tier": "basic", "risk_impact": "low"},
        ]

        breakdown = score_service._calculate_breakdown(items)
        score = score_service._calculate_simple_score(breakdown)

        assert score == 0.0

    def test_partial_score(
        self,
        score_service: ScoreService,
        sample_assessment_items: list[dict],
    ) -> None:
        """Mixed items result in partial score."""
        breakdown = score_service._calculate_breakdown(sample_assessment_items)
        score = score_service._calculate_simple_score(breakdown)

        # 2 compliant + 0.5 * 1 partial = 2.5 / 4 = 0.625
        assert score == pytest.approx(0.625, rel=0.01)

    def test_empty_items(self, score_service: ScoreService) -> None:
        """Empty items result in zero score."""
        breakdown = score_service._calculate_breakdown([])
        score = score_service._calculate_simple_score(breakdown)

        assert score == 0.0


# =============================================================================
# Weighted Score Tests
# =============================================================================


class TestWeightedScore:
    """Tests for tier-weighted score calculation."""

    def test_weighted_score_all_basic(
        self,
        score_service: ScoreService,
        all_compliant_items: list[dict],
    ) -> None:
        """All basic tier items result in 1.0 weighted score when compliant."""
        score = score_service._calculate_weighted_score(all_compliant_items)
        assert score == 1.0

    def test_weighted_score_mixed_tiers(
        self,
        score_service: ScoreService,
        mixed_tier_items: list[dict],
    ) -> None:
        """Mixed tier items are weighted correctly."""
        score = score_service._calculate_weighted_score(mixed_tier_items)

        # Calculation:
        # basic-1: compliant, weight 1.0, score 1.0 -> 1.0 * 1.0 = 1.0
        # basic-2: compliant, weight 1.0, score 1.0 -> 1.0 * 1.0 = 1.0
        # standard-1: compliant, weight 1.5, score 1.0 -> 1.5 * 1.0 = 1.5
        # standard-2: non_compliant, weight 1.5, score 0.0 -> 1.5 * 0.0 = 0.0
        # advanced-1: non_compliant, weight 2.0, score 0.0 -> 2.0 * 0.0 = 0.0
        # Total weight: 1.0 + 1.0 + 1.5 + 1.5 + 2.0 = 7.0
        # Achieved: 1.0 + 1.0 + 1.5 + 0 + 0 = 3.5
        # Score: 3.5 / 7.0 = 0.5

        assert score == pytest.approx(0.5, rel=0.01)

    def test_custom_weights(
        self,
        custom_score_service: ScoreService,
        mixed_tier_items: list[dict],
    ) -> None:
        """Custom weights change the weighted score."""
        score = custom_score_service._calculate_weighted_score(mixed_tier_items)

        # With custom weights (standard=2.0, advanced=3.0):
        # Total weight: 1.0 + 1.0 + 2.0 + 2.0 + 3.0 = 9.0
        # Achieved: 1.0 + 1.0 + 2.0 + 0 + 0 = 4.0
        # Score: 4.0 / 9.0 ≈ 0.444

        assert score == pytest.approx(0.444, rel=0.01)


# =============================================================================
# Risk-Adjusted Score Tests
# =============================================================================


class TestRiskAdjustedScore:
    """Tests for risk-adjusted score calculation."""

    def test_risk_adjusted_with_low_risk(
        self,
        score_service: ScoreService,
    ) -> None:
        """Low risk items have multiplier of 1.0."""
        items = [
            {"requirement_id": "req-1", "status": "compliant", "risk_impact": "low"},
            {"requirement_id": "req-2", "status": "non_compliant", "risk_impact": "low"},
        ]

        score = score_service._calculate_risk_adjusted_score(items)

        # Both have weight 1.0, 50% compliant
        assert score == pytest.approx(0.5, rel=0.01)

    def test_risk_adjusted_with_high_risk(
        self,
        score_service: ScoreService,
    ) -> None:
        """High risk non-compliance has bigger impact."""
        items = [
            {"requirement_id": "req-1", "status": "compliant", "risk_impact": "low"},  # weight 1.0
            {"requirement_id": "req-2", "status": "non_compliant", "risk_impact": "high"},  # weight 1.5
        ]

        score = score_service._calculate_risk_adjusted_score(items)

        # Total weight: 1.0 + 1.5 = 2.5
        # Achieved: 1.0 + 0 = 1.0
        # Score: 1.0 / 2.5 = 0.4

        assert score == pytest.approx(0.4, rel=0.01)

    def test_critical_risk_non_compliance(
        self,
        score_service: ScoreService,
    ) -> None:
        """Critical risk non-compliance significantly impacts score."""
        items = [
            {"requirement_id": "req-1", "status": "compliant", "risk_impact": "low"},  # weight 1.0
            {"requirement_id": "req-2", "status": "compliant", "risk_impact": "low"},  # weight 1.0
            {"requirement_id": "req-3", "status": "non_compliant", "risk_impact": "critical"},  # weight 2.0
        ]

        score = score_service._calculate_risk_adjusted_score(items)

        # Total weight: 1.0 + 1.0 + 2.0 = 4.0
        # Achieved: 1.0 + 1.0 + 0 = 2.0
        # Score: 2.0 / 4.0 = 0.5

        assert score == pytest.approx(0.5, rel=0.01)


# =============================================================================
# Risk Level Tests
# =============================================================================


class TestRiskLevel:
    """Tests for risk level determination."""

    def test_low_risk_level(self, score_service: ScoreService) -> None:
        """High score with low non-compliance rate = low risk."""
        risk_level = score_service._determine_risk_level(
            score=0.95,
            non_compliant=1,
            total=20,
        )

        assert risk_level == "low"

    def test_medium_risk_level(self, score_service: ScoreService) -> None:
        """Medium score = medium risk."""
        risk_level = score_service._determine_risk_level(
            score=0.75,
            non_compliant=3,
            total=20,
        )

        assert risk_level == "medium"

    def test_high_risk_level(self, score_service: ScoreService) -> None:
        """Low score = high risk."""
        risk_level = score_service._determine_risk_level(
            score=0.60,
            non_compliant=6,
            total=20,
        )

        assert risk_level == "high"

    def test_critical_risk_level(self, score_service: ScoreService) -> None:
        """Very low score = critical risk."""
        risk_level = score_service._determine_risk_level(
            score=0.40,
            non_compliant=10,
            total=20,
        )

        assert risk_level == "critical"


# =============================================================================
# Score Result Tests
# =============================================================================


class TestScoreResult:
    """Tests for complete score result calculation."""

    @pytest.mark.asyncio
    async def test_calculate_entity_score(
        self,
        score_service: ScoreService,
        sample_assessment_items: list[dict],
    ) -> None:
        """Calculate complete entity score."""
        # Mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(fetchall=lambda: [], fetchone=lambda: None))

        result = await score_service.calculate_entity_score(
            db=mock_db,
            entity_id="test-entity-123",
            assessment_items=sample_assessment_items,
        )

        assert isinstance(result, ScoreResult)
        assert result.entity_id == "test-entity-123"
        assert 0 <= result.overall_score <= 1
        assert 0 <= result.weighted_score <= 1
        assert 0 <= result.risk_adjusted_score <= 1
        assert result.risk_level in ("low", "medium", "high", "critical")
        assert isinstance(result.breakdown, ScoreBreakdown)

    @pytest.mark.asyncio
    async def test_score_result_with_empty_items(
        self,
        score_service: ScoreService,
    ) -> None:
        """Empty items result in zero scores."""
        mock_db = AsyncMock()

        result = await score_service.calculate_entity_score(
            db=mock_db,
            entity_id="test-entity-123",
            assessment_items=[],
        )

        assert result.overall_score == 0.0
        assert result.weighted_score == 0.0
        assert result.risk_adjusted_score == 0.0


# =============================================================================
# Score History Tests
# =============================================================================


class TestScoreHistory:
    """Tests for score history tracking."""

    @pytest.mark.asyncio
    async def test_get_score_history(
        self,
        score_service: ScoreService,
    ) -> None:
        """Get score history from database."""
        mock_db = AsyncMock()

        # Mock database response
        mock_rows = [
            MagicMock(
                id="score-1",
                score=0.85,
                previous_score=0.80,
                change=0.05,
                recorded_at=datetime.now(UTC),
            ),
            MagicMock(
                id="score-2",
                score=0.80,
                previous_score=0.75,
                change=0.05,
                recorded_at=datetime.now(UTC),
            ),
        ]
        mock_db.execute = AsyncMock(return_value=MagicMock(fetchall=lambda: mock_rows))

        history = await score_service.get_score_history(
            db=mock_db,
            entity_id="test-entity-123",
            score_type=ScoreType.OVERALL,
            limit=30,
        )

        assert len(history) == 2
        assert history[0]["score"] == 0.85
        assert history[1]["score"] == 0.80


# =============================================================================
# Score Recording Tests
# =============================================================================


class TestScoreRecording:
    """Tests for score recording."""

    @pytest.mark.asyncio
    async def test_record_score(
        self,
        score_service: ScoreService,
        sample_assessment_items: list[dict],
    ) -> None:
        """Record score updates database correctly."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(fetchone=lambda: None))

        # Calculate a score first
        result = await score_service.calculate_entity_score(
            db=mock_db,
            entity_id="test-entity-123",
            assessment_items=sample_assessment_items,
        )

        # Reset mock
        mock_db.execute.reset_mock()

        # Record the score
        await score_service.record_score(
            db=mock_db,
            entity_id="test-entity-123",
            score_result=result,
            assessment_id="assessment-123",
        )

        # Should have called execute for:
        # - Overall score history insert
        # - Update entity scores
        assert mock_db.execute.call_count >= 2


# =============================================================================
# Edge Cases
# =============================================================================


class TestScoreEdgeCases:
    """Tests for edge cases in score calculation."""

    def test_all_not_applicable(self, score_service: ScoreService) -> None:
        """All N/A items result in zero total requirements."""
        items = [
            {"requirement_id": "req-1", "status": "not_applicable", "requirement_tier": "basic"},
            {"requirement_id": "req-2", "status": "not_applicable", "requirement_tier": "basic"},
        ]

        breakdown = score_service._calculate_breakdown(items)

        assert breakdown.total_requirements == 0
        assert breakdown.not_applicable == 2

    def test_missing_tier_defaults_to_basic(self, score_service: ScoreService) -> None:
        """Missing tier defaults to basic weight."""
        items = [
            {"requirement_id": "req-1", "status": "compliant"},  # No tier specified
        ]

        score = score_service._calculate_weighted_score(items)

        # Should still calculate with default basic weight
        assert score == 1.0

    def test_unknown_status_treated_as_zero(self, score_service: ScoreService) -> None:
        """Unknown status treated as non-compliant."""
        items = [
            {"requirement_id": "req-1", "status": "unknown", "requirement_tier": "basic"},
        ]

        breakdown = score_service._calculate_breakdown(items)

        # Unknown status doesn't increment any counter but adds to total
        assert breakdown.total_requirements == 1
        assert breakdown.compliant == 0

