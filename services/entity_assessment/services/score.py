"""
Compliance Score Calculation Service
====================================

Engine for calculating entity compliance scores.

Score Components:
- Overall compliance rate
- Tier-weighted score
- Risk-adjusted score
- Jurisdiction-specific scores
- Sector-specific scores

Version: 0.1.0
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.entity_assessment.models.score import ScoreType
from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# Score Configuration
# =============================================================================


@dataclass
class ScoreWeights:
    """Weights for score calculation."""

    # Tier weights (higher tiers more important)
    tier_weights: dict[str, float] = field(
        default_factory=lambda: {
            "basic": 1.0,
            "standard": 1.5,
            "advanced": 2.0,
        }
    )

    # Status weights
    status_weights: dict[str, float] = field(
        default_factory=lambda: {
            "compliant": 1.0,
            "partial": 0.5,
            "remediation": 0.3,
            "non_compliant": 0.0,
            "pending": 0.0,
            "not_applicable": None,  # Excluded from calculation
        }
    )

    # Risk impact multipliers
    risk_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            "low": 1.0,
            "medium": 1.2,
            "high": 1.5,
            "critical": 2.0,
        }
    )


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown."""

    # Counts
    total_requirements: int = 0
    compliant: int = 0
    non_compliant: int = 0
    partial: int = 0
    pending: int = 0
    not_applicable: int = 0

    # By tier
    by_tier: dict[str, dict[str, int]] = field(default_factory=dict)

    # By jurisdiction
    by_jurisdiction: dict[str, float] = field(default_factory=dict)

    # By sector
    by_sector: dict[str, float] = field(default_factory=dict)

    # By regulation
    by_regulation: dict[str, float] = field(default_factory=dict)


@dataclass
class ScoreResult:
    """Complete score calculation result."""

    entity_id: str
    calculated_at: datetime

    # Main scores
    overall_score: float  # 0.0 to 1.0
    weighted_score: float  # Tier-weighted
    risk_adjusted_score: float  # Risk-adjusted

    # Risk level
    risk_level: str  # low, medium, high, critical

    # Breakdown
    breakdown: ScoreBreakdown

    # Change from previous
    previous_score: float | None = None
    score_change: float | None = None
    score_trend: str | None = None  # improving, declining, stable

    # Metadata
    calculation_method: str = "standard"
    confidence: float = 1.0


# =============================================================================
# Score Service
# =============================================================================


class ScoreService:
    """
    Service for calculating and tracking compliance scores.

    Calculation Methods:
    1. Simple: compliant / total (excluding N/A)
    2. Weighted: Considers tier importance
    3. Risk-Adjusted: Factors in risk impact of non-compliance
    """

    def __init__(
        self,
        weights: ScoreWeights | None = None,
    ) -> None:
        """
        Initialize the score service.

        Args:
            weights: Custom scoring weights
        """
        self.weights = weights or ScoreWeights()

    async def calculate_entity_score(
        self,
        db: AsyncSession,
        entity_id: str,
        assessment_items: list[dict[str, Any]] | None = None,
    ) -> ScoreResult:
        """
        Calculate comprehensive compliance score for an entity.

        Args:
            db: Database session
            entity_id: Entity UUID
            assessment_items: Pre-fetched items (or will be queried)

        Returns:
            ScoreResult with all scores and breakdown
        """
        # Get assessment items if not provided
        if assessment_items is None:
            assessment_items = await self._get_latest_assessment_items(db, entity_id)

        if not assessment_items:
            return ScoreResult(
                entity_id=entity_id,
                calculated_at=datetime.now(UTC),
                overall_score=0.0,
                weighted_score=0.0,
                risk_adjusted_score=0.0,
                risk_level="unknown",
                breakdown=ScoreBreakdown(),
            )

        # Calculate breakdown
        breakdown = self._calculate_breakdown(assessment_items)

        # Calculate scores
        overall = self._calculate_simple_score(breakdown)
        weighted = self._calculate_weighted_score(assessment_items)
        risk_adjusted = self._calculate_risk_adjusted_score(assessment_items)

        # Determine risk level
        risk_level = self._determine_risk_level(
            overall,
            breakdown.non_compliant,
            breakdown.total_requirements,
        )

        # Get previous score for trend
        previous = await self._get_previous_score(db, entity_id)
        score_change = None
        trend = None

        if previous is not None:
            score_change = overall - previous
            if score_change > 0.01:
                trend = "improving"
            elif score_change < -0.01:
                trend = "declining"
            else:
                trend = "stable"

        result = ScoreResult(
            entity_id=entity_id,
            calculated_at=datetime.now(UTC),
            overall_score=round(overall, 4),
            weighted_score=round(weighted, 4),
            risk_adjusted_score=round(risk_adjusted, 4),
            risk_level=risk_level,
            breakdown=breakdown,
            previous_score=previous,
            score_change=round(score_change, 4) if score_change else None,
            score_trend=trend,
        )

        logger.info(
            "score_calculated",
            entity_id=entity_id,
            overall=result.overall_score,
            weighted=result.weighted_score,
            risk_level=risk_level,
        )

        return result

    def _calculate_breakdown(
        self,
        items: list[dict[str, Any]],
    ) -> ScoreBreakdown:
        """Calculate score breakdown from items."""
        breakdown = ScoreBreakdown()

        by_tier: dict[str, dict[str, int]] = {
            "basic": {"total": 0, "compliant": 0},
            "standard": {"total": 0, "compliant": 0},
            "advanced": {"total": 0, "compliant": 0},
        }

        by_jurisdiction: dict[str, dict[str, int]] = {}
        by_regulation: dict[str, dict[str, int]] = {}

        for item in items:
            status = item.get("status", "pending")
            tier = item.get("requirement_tier", "basic")
            regulation = item.get("regulation_id", "unknown")
            jurisdictions = item.get("jurisdictions", [])

            # Count by status
            if status == "compliant":
                breakdown.compliant += 1
            elif status == "non_compliant":
                breakdown.non_compliant += 1
            elif status == "partial":
                breakdown.partial += 1
            elif status == "pending":
                breakdown.pending += 1
            elif status == "not_applicable":
                breakdown.not_applicable += 1
                continue  # Skip N/A from total

            breakdown.total_requirements += 1

            # By tier
            tier_lower = tier.lower() if tier else "basic"
            if tier_lower not in by_tier:
                by_tier[tier_lower] = {"total": 0, "compliant": 0}
            by_tier[tier_lower]["total"] += 1
            if status == "compliant":
                by_tier[tier_lower]["compliant"] += 1

            # By jurisdiction
            for j in jurisdictions or []:
                if j not in by_jurisdiction:
                    by_jurisdiction[j] = {"total": 0, "compliant": 0}
                by_jurisdiction[j]["total"] += 1
                if status == "compliant":
                    by_jurisdiction[j]["compliant"] += 1

            # By regulation
            if regulation:
                if regulation not in by_regulation:
                    by_regulation[regulation] = {"total": 0, "compliant": 0}
                by_regulation[regulation]["total"] += 1
                if status == "compliant":
                    by_regulation[regulation]["compliant"] += 1

        breakdown.by_tier = by_tier

        # Convert to scores
        breakdown.by_jurisdiction = {
            j: v["compliant"] / v["total"] if v["total"] > 0 else 0
            for j, v in by_jurisdiction.items()
        }
        breakdown.by_regulation = {
            r: v["compliant"] / v["total"] if v["total"] > 0 else 0
            for r, v in by_regulation.items()
        }

        return breakdown

    def _calculate_simple_score(self, breakdown: ScoreBreakdown) -> float:
        """Calculate simple compliance rate."""
        if breakdown.total_requirements == 0:
            return 0.0

        # Compliant + partial (weighted)
        score = (breakdown.compliant + (breakdown.partial * 0.5)) / breakdown.total_requirements

        return min(1.0, max(0.0, score))

    def _calculate_weighted_score(
        self,
        items: list[dict[str, Any]],
    ) -> float:
        """Calculate tier-weighted score."""
        total_weight = 0.0
        achieved_weight = 0.0

        for item in items:
            status = item.get("status", "pending")
            tier = item.get("requirement_tier", "basic")

            if status == "not_applicable":
                continue

            tier_lower = tier.lower() if tier else "basic"
            weight = self.weights.tier_weights.get(tier_lower, 1.0)
            total_weight += weight

            status_score = self.weights.status_weights.get(status, 0.0)
            if status_score is not None:
                achieved_weight += weight * status_score

        if total_weight == 0:
            return 0.0

        return achieved_weight / total_weight

    def _calculate_risk_adjusted_score(
        self,
        items: list[dict[str, Any]],
    ) -> float:
        """Calculate risk-adjusted score."""
        total_weight = 0.0
        achieved_weight = 0.0

        for item in items:
            status = item.get("status", "pending")
            risk_impact = item.get("risk_impact", "medium")

            if status == "not_applicable":
                continue

            # Risk multiplier affects weight
            risk_mult = self.weights.risk_multipliers.get(risk_impact, 1.0)
            weight = risk_mult
            total_weight += weight

            status_score = self.weights.status_weights.get(status, 0.0)
            if status_score is not None:
                achieved_weight += weight * status_score

        if total_weight == 0:
            return 0.0

        return achieved_weight / total_weight

    def _determine_risk_level(
        self,
        score: float,
        non_compliant: int,
        total: int,
    ) -> str:
        """Determine overall risk level."""
        # Non-compliance rate
        nc_rate = non_compliant / total if total > 0 else 0

        if score < 0.5 or nc_rate > 0.3:
            return "critical"
        elif score < 0.7 or nc_rate > 0.2:
            return "high"
        elif score < 0.85 or nc_rate > 0.1:
            return "medium"
        else:
            return "low"

    async def _get_latest_assessment_items(
        self,
        db: AsyncSession,
        entity_id: str,
    ) -> list[dict[str, Any]]:
        """Get items from the latest completed assessment."""
        query = text("""
            SELECT 
                ai.requirement_id,
                ai.status,
                ai.requirement_tier,
                ai.regulation_id,
                ai.risk_impact,
                ai.score
            FROM core.assessment_items ai
            JOIN core.assessments a ON ai.assessment_id = a.id
            WHERE a.entity_id = :entity_id
              AND a.status = 'completed'
            ORDER BY a.completed_at DESC
        """)

        result = await db.execute(query, {"entity_id": entity_id})
        rows = result.fetchall()

        return [
            {
                "requirement_id": row.requirement_id,
                "status": row.status,
                "requirement_tier": row.requirement_tier,
                "regulation_id": row.regulation_id,
                "risk_impact": row.risk_impact,
                "score": float(row.score) if row.score else None,
            }
            for row in rows
        ]

    async def _get_previous_score(
        self,
        db: AsyncSession,
        entity_id: str,
    ) -> float | None:
        """Get the most recent previous score."""
        query = text("""
            SELECT score FROM core.score_history
            WHERE entity_id = :entity_id
              AND score_type = 'overall'
            ORDER BY recorded_at DESC
            LIMIT 1 OFFSET 1
        """)

        result = await db.execute(query, {"entity_id": entity_id})
        row = result.fetchone()

        if row:
            return float(row.score)
        return None

    async def record_score(
        self,
        db: AsyncSession,
        entity_id: str,
        score_result: ScoreResult,
        assessment_id: str | None = None,
    ) -> None:
        """
        Record score in history.

        Args:
            db: Database session
            entity_id: Entity UUID
            score_result: Calculated score
            assessment_id: Optional assessment that triggered this
        """
        # Record overall score
        await self._insert_score_history(
            db,
            entity_id=entity_id,
            score_type=ScoreType.OVERALL,
            score=score_result.overall_score,
            previous_score=score_result.previous_score,
            breakdown=score_result.breakdown.by_tier,
            assessment_id=assessment_id,
            total=score_result.breakdown.total_requirements,
            compliant=score_result.breakdown.compliant,
            non_compliant=score_result.breakdown.non_compliant,
        )

        # Record jurisdiction scores
        for jurisdiction, score in score_result.breakdown.by_jurisdiction.items():
            await self._insert_score_history(
                db,
                entity_id=entity_id,
                score_type=ScoreType.JURISDICTION,
                scope=jurisdiction,
                score=score,
                assessment_id=assessment_id,
            )

        # Update entity record
        await self._update_entity_scores(
            db,
            entity_id=entity_id,
            compliance_score=score_result.overall_score,
            risk_score=1.0 - score_result.risk_adjusted_score,  # Risk score is inverse
            breakdown=score_result.breakdown,
        )

        logger.info(
            "score_recorded",
            entity_id=entity_id,
            score=score_result.overall_score,
        )

    async def _insert_score_history(
        self,
        db: AsyncSession,
        entity_id: str,
        score_type: ScoreType,
        score: float,
        scope: str | None = None,
        previous_score: float | None = None,
        breakdown: dict[str, Any] | None = None,
        assessment_id: str | None = None,
        total: int | None = None,
        compliant: int | None = None,
        non_compliant: int | None = None,
    ) -> None:
        """Insert a score history record."""
        change = None
        change_pct = None

        if previous_score is not None:
            change = score - previous_score
            if previous_score > 0:
                change_pct = (change / previous_score) * 100

        query = text("""
            INSERT INTO core.score_history (
                id, entity_id, score_type, scope, score, previous_score,
                change, change_percentage, breakdown, assessment_id,
                total_requirements, compliant_count, non_compliant_count,
                recorded_at
            ) VALUES (
                :id, :entity_id, :score_type, :scope, :score, :previous_score,
                :change, :change_percentage, :breakdown, :assessment_id,
                :total, :compliant, :non_compliant,
                :recorded_at
            )
        """)

        await db.execute(
            query,
            {
                "id": str(uuid.uuid4()),
                "entity_id": entity_id,
                "score_type": score_type.value,
                "scope": scope,
                "score": score,
                "previous_score": previous_score,
                "change": change,
                "change_percentage": change_pct,
                "breakdown": breakdown,
                "assessment_id": assessment_id,
                "total": total,
                "compliant": compliant,
                "non_compliant": non_compliant,
                "recorded_at": datetime.now(UTC),
            },
        )

    async def _update_entity_scores(
        self,
        db: AsyncSession,
        entity_id: str,
        compliance_score: float,
        risk_score: float,
        breakdown: ScoreBreakdown,
    ) -> None:
        """Update entity's cached scores."""
        query = text("""
            UPDATE core.entities
            SET compliance_score = :compliance_score,
                risk_score = :risk_score,
                total_requirements = :total,
                compliant_requirements = :compliant,
                non_compliant_requirements = :non_compliant,
                pending_requirements = :pending,
                updated_at = :updated_at
            WHERE id = :entity_id
        """)

        await db.execute(
            query,
            {
                "entity_id": entity_id,
                "compliance_score": compliance_score,
                "risk_score": risk_score,
                "total": breakdown.total_requirements,
                "compliant": breakdown.compliant,
                "non_compliant": breakdown.non_compliant,
                "pending": breakdown.pending,
                "updated_at": datetime.now(UTC),
            },
        )

    async def get_score_history(
        self,
        db: AsyncSession,
        entity_id: str,
        score_type: ScoreType = ScoreType.OVERALL,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Get score history for an entity.

        Args:
            db: Database session
            entity_id: Entity UUID
            score_type: Type of score to retrieve
            limit: Maximum records

        Returns:
            List of historical scores
        """
        query = text("""
            SELECT *
            FROM core.score_history
            WHERE entity_id = :entity_id
              AND score_type = :score_type
            ORDER BY recorded_at DESC
            LIMIT :limit
        """)

        result = await db.execute(
            query,
            {
                "entity_id": entity_id,
                "score_type": score_type.value,
                "limit": limit,
            },
        )

        return [
            {
                "id": str(row.id),
                "score": float(row.score),
                "previous_score": float(row.previous_score) if row.previous_score else None,
                "change": float(row.change) if row.change else None,
                "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
            }
            for row in result.fetchall()
        ]
