"""
Compliance Scores Routes
========================

API endpoints for compliance score calculation and retrieval.

Version: 0.1.0
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import User, get_current_user
from shared.database.postgres import get_postgres_session
from shared.database.redis import RedisClient
from shared.logging import get_logger
from shared.models.compliance import ComplianceScore, ComplianceSummary


logger = get_logger(__name__)

router = APIRouter()


@router.get("/{entity_id}", response_model=ComplianceScore)
async def get_entity_score(
    entity_id: str,
    db: AsyncSession = Depends(get_postgres_session),
) -> ComplianceScore:
    """
    Get compliance score for an entity.

    Calculates the score from completed assessments.
    """
    # Try cache first
    cache_key = f"compliance_score:{entity_id}"
    cached = await RedisClient.get_cached(cache_key)
    if cached and isinstance(cached, dict):
        return ComplianceScore(**cached)

    # Get entity
    entity_query = text("""
        SELECT id, name, compliance_score, compliance_tier
        FROM core.entities
        WHERE id = :entity_id AND deleted_at IS NULL
    """)
    result = await db.execute(entity_query, {"entity_id": entity_id})
    entity = result.fetchone()

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        )

    # Get assessment statistics
    stats_query = text("""
        SELECT 
            COUNT(*) as total,
            AVG(overall_score) as avg_score,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved,
            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected
        FROM core.assessments
        WHERE entity_id = :entity_id
    """)
    stats_result = await db.execute(stats_query, {"entity_id": entity_id})
    stats = stats_result.fetchone()

    # Calculate score breakdown
    overall_score = float(entity.compliance_score) if entity.compliance_score else 0.0

    # If no stored score, calculate from assessments
    if not entity.compliance_score and stats and stats.avg_score:  # type: ignore[union-attr]
        overall_score = float(stats.avg_score)  # type: ignore[union-attr]

    # Calculate percentage
    overall_percentage = (overall_score / 5.0) * 100 if overall_score else 0.0

    score = ComplianceScore(
        entity_id=entity_id,
        overall_score=overall_score,
        overall_percentage=overall_percentage,
        tier_scores={entity.compliance_tier: overall_score},
        total_requirements=0,  # Would come from graph service
        compliant_count=stats.approved if stats else 0,  # type: ignore[union-attr]
        non_compliant_count=stats.rejected if stats else 0,  # type: ignore[union-attr]
        not_assessed_count=0,
        calculated_at=datetime.now(UTC),
    )

    # Cache for 5 minutes
    await RedisClient.set_cached(cache_key, score.model_dump(mode="json"), ttl_seconds=300)

    logger.debug(
        "compliance_score_calculated",
        entity_id=entity_id,
        score=overall_score,
    )

    return score


@router.post("/{entity_id}/calculate", response_model=ComplianceScore)
async def calculate_entity_score(
    entity_id: str,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> ComplianceScore:
    """
    Recalculate and update compliance score for an entity.

    This fetches data from assessments and the compliance graph
    to compute a comprehensive score.

    Requires authentication.
    """
    # Get all approved assessments
    assessments_query = text("""
        SELECT overall_score, criterion_scores
        FROM core.assessments
        WHERE entity_id = :entity_id
        AND status = 'approved'
        AND overall_score IS NOT NULL
        ORDER BY completed_at DESC
        LIMIT 10
    """)
    result = await db.execute(assessments_query, {"entity_id": entity_id})
    assessments = result.fetchall()

    if not assessments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No completed assessments to calculate score from",
        )

    # Calculate weighted average (more recent = higher weight)
    total_weight = 0.0
    weighted_sum = 0.0

    for i, assessment in enumerate(assessments):
        weight = 1.0 / (i + 1)  # Newer assessments have higher weight
        weighted_sum += float(assessment.overall_score) * weight
        total_weight += weight

    calculated_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Update entity's compliance score
    update_query = text("""
        UPDATE core.entities
        SET compliance_score = :score, updated_at = :updated_at
        WHERE id = :entity_id
        RETURNING compliance_tier
    """)
    result = await db.execute(
        update_query,
        {
            "entity_id": entity_id,
            "score": calculated_score,
            "updated_at": datetime.now(UTC),
        },
    )
    row = result.fetchone()

    # Invalidate cache
    cache_key = f"compliance_score:{entity_id}"
    await RedisClient.delete_cached(cache_key)

    logger.info(
        "compliance_score_updated",
        entity_id=entity_id,
        score=calculated_score,
        assessments_used=len(assessments),
        user_id=current_user.id,
    )

    return ComplianceScore(
        entity_id=entity_id,
        overall_score=calculated_score,
        overall_percentage=(calculated_score / 5.0) * 100,
        tier_scores={row.compliance_tier: calculated_score} if row else {},  # type: ignore[union-attr]
        total_requirements=0,
        compliant_count=len(assessments),
        calculated_at=datetime.now(UTC),
    )


@router.get("/{entity_id}/summary", response_model=ComplianceSummary)
async def get_entity_compliance_summary(
    entity_id: str,
    db: AsyncSession = Depends(get_postgres_session),
) -> ComplianceSummary:
    """
    Get comprehensive compliance summary for an entity.

    Includes score, tier, gaps, and assessment status.
    """
    # Get entity details
    entity_query = text("""
        SELECT id, name, compliance_tier, compliance_score, 
               risk_score, last_assessment_at
        FROM core.entities
        WHERE id = :entity_id AND deleted_at IS NULL
    """)
    result = await db.execute(entity_query, {"entity_id": entity_id})
    entity = result.fetchone()

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        )

    # Get assessment counts
    assessment_query = text("""
        SELECT 
            COUNT(CASE WHEN status IN ('draft', 'in_progress') THEN 1 END) as in_progress
        FROM core.assessments
        WHERE entity_id = :entity_id
    """)
    assessment_result = await db.execute(assessment_query, {"entity_id": entity_id})
    assessment_stats = assessment_result.fetchone()

    # Calculate next assessment due (example: 1 year from last)
    next_due = None
    if entity.last_assessment_at:
        from datetime import timedelta

        next_due = entity.last_assessment_at + timedelta(days=365)

    return ComplianceSummary(
        entity_id=entity_id,
        entity_name=entity.name,
        compliance_tier=entity.compliance_tier,
        compliance_score=float(entity.compliance_score) if entity.compliance_score else None,
        risk_score=float(entity.risk_score) if entity.risk_score else None,
        total_gaps=0,  # Would come from graph service
        critical_gaps=0,
        high_priority_gaps=0,
        last_assessment_date=entity.last_assessment_at,
        next_assessment_due=next_due,
        assessments_in_progress=assessment_stats.in_progress if assessment_stats else 0,  # type: ignore[union-attr]
        score_trend="stable",
    )


@router.get("/{entity_id}/history")
async def get_score_history(
    entity_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_postgres_session),
) -> list[dict[str, Any]]:
    """
    Get compliance score history for an entity.

    Returns historical scores from completed assessments.
    """
    query = text("""
        SELECT 
            id, overall_score, assessment_type,
            completed_at
        FROM core.assessments
        WHERE entity_id = :entity_id
        AND status = 'approved'
        AND overall_score IS NOT NULL
        ORDER BY completed_at DESC
        LIMIT :limit
    """)

    result = await db.execute(query, {"entity_id": entity_id, "limit": limit})
    rows = result.fetchall()

    history = [
        {
            "assessment_id": str(row.id),
            "score": float(row.overall_score),
            "assessment_type": row.assessment_type,
            "date": row.completed_at.isoformat() if row.completed_at else None,
        }
        for row in rows
    ]

    return history
