"""
Compliance Status Routes
========================

API endpoints for compliance status and gap analysis.

Version: 0.1.0
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from shared.auth import get_current_user, User
from shared.logging import get_logger

from services.compliance_graph.queries.compliance import (
    ComplianceQueryEngine,
    ComplianceGap,
    ComplianceScore,
    ComplianceReport,
)
from services.compliance_graph.schema.nodes import ComplianceStatus

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================


class ComplianceScoreResponse(BaseModel):
    """Compliance score summary."""

    total_requirements: int
    compliant: int
    non_compliant: int
    partial: int
    pending: int
    exempt: int
    unknown: int
    compliance_rate: float
    risk_score: float


class ComplianceGapResponse(BaseModel):
    """A compliance gap."""

    requirement_id: str
    requirement_text: str
    regulation_id: str
    tier: str
    status: str
    penalty_risk: float | None
    remediation_priority: int


class ComplianceReportResponse(BaseModel):
    """Full compliance report."""

    entity_id: str
    entity_name: str
    generated_at: str

    score: ComplianceScoreResponse
    by_jurisdiction: dict[str, ComplianceScoreResponse]
    by_tier: dict[str, ComplianceScoreResponse]

    critical_gaps: list[ComplianceGapResponse]
    total_gaps: int


class UpdateComplianceRequest(BaseModel):
    """Request to update compliance status."""

    entity_id: str
    requirement_id: str
    status: ComplianceStatus
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    assessor: str | None = None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/score/{entity_id}", response_model=ComplianceScoreResponse)
async def get_compliance_score(
    entity_id: str,
    jurisdiction: str | None = Query(default=None),
    regulation_id: str | None = Query(default=None),
) -> ComplianceScoreResponse:
    """
    Get compliance score for an entity.

    Returns counts and rates for each compliance status.

    Optional filters:
    - jurisdiction: Filter to specific jurisdiction
    - regulation_id: Filter to specific regulation
    """
    engine = ComplianceQueryEngine()

    try:
        score = await engine.get_compliance_score(
            entity_id,
            jurisdiction=jurisdiction,
            regulation_id=regulation_id,
        )

        return ComplianceScoreResponse(
            total_requirements=score.total_requirements,
            compliant=score.compliant,
            non_compliant=score.non_compliant,
            partial=score.partial,
            pending=score.pending,
            exempt=score.exempt,
            unknown=score.unknown,
            compliance_rate=score.compliance_rate,
            risk_score=score.risk_score,
        )

    except Exception as e:
        logger.error("compliance_score_failed", entity_id=entity_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get compliance score: {str(e)}",
        )


@router.get("/gaps/{entity_id}", response_model=list[ComplianceGapResponse])
async def get_compliance_gaps(
    entity_id: str,
    include_partial: bool = Query(default=True),
    include_unknown: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ComplianceGapResponse]:
    """
    Get compliance gaps for an entity.

    Returns requirements where entity is non-compliant, partial, or unknown,
    ordered by priority (tier + penalty risk).

    Args:
        entity_id: Entity ID
        include_partial: Include partially compliant as gaps
        include_unknown: Include unknown status as gaps
        limit: Maximum gaps to return
    """
    engine = ComplianceQueryEngine()

    try:
        gaps = await engine.get_compliance_gaps(
            entity_id,
            include_partial=include_partial,
            include_unknown=include_unknown,
        )

        return [
            ComplianceGapResponse(
                requirement_id=g.requirement_id,
                requirement_text=g.requirement_text,
                regulation_id=g.regulation_id,
                tier=g.tier,
                status=g.status.value,
                penalty_risk=g.penalty_risk,
                remediation_priority=g.remediation_priority,
            )
            for g in gaps[:limit]
        ]

    except Exception as e:
        logger.error("compliance_gaps_failed", entity_id=entity_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get compliance gaps: {str(e)}",
        )


@router.get("/report/{entity_id}", response_model=ComplianceReportResponse)
async def get_compliance_report(
    entity_id: str,
) -> ComplianceReportResponse:
    """
    Generate a comprehensive compliance report for an entity.

    Includes:
    - Overall compliance score
    - Score breakdown by jurisdiction and tier
    - Critical gaps requiring immediate attention
    - Total gap count
    """
    engine = ComplianceQueryEngine()

    try:
        report = await engine.generate_compliance_report(entity_id)

        def score_to_response(s: ComplianceScore) -> ComplianceScoreResponse:
            return ComplianceScoreResponse(
                total_requirements=s.total_requirements,
                compliant=s.compliant,
                non_compliant=s.non_compliant,
                partial=s.partial,
                pending=s.pending,
                exempt=s.exempt,
                unknown=s.unknown,
                compliance_rate=s.compliance_rate,
                risk_score=s.risk_score,
            )

        return ComplianceReportResponse(
            entity_id=report.entity_id,
            entity_name=report.entity_name,
            generated_at=report.generated_at.isoformat(),
            score=score_to_response(report.score),
            by_jurisdiction={
                j: score_to_response(s)
                for j, s in report.by_jurisdiction.items()
            },
            by_tier={
                t: score_to_response(s)
                for t, s in report.by_tier.items()
            },
            critical_gaps=[
                ComplianceGapResponse(
                    requirement_id=g.requirement_id,
                    requirement_text=g.requirement_text,
                    regulation_id=g.regulation_id,
                    tier=g.tier,
                    status=g.status.value,
                    penalty_risk=g.penalty_risk,
                    remediation_priority=g.remediation_priority,
                )
                for g in report.critical_gaps
            ],
            total_gaps=len(report.all_gaps),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error("compliance_report_failed", entity_id=entity_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}",
        )


@router.post("/update", status_code=status.HTTP_200_OK)
async def update_compliance_status(
    request: UpdateComplianceRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Update compliance status for an entity-requirement pair.

    Creates or updates the ComplianceState node and relationships.

    Requires authentication.
    """
    engine = ComplianceQueryEngine()

    try:
        result = await engine.update_compliance_state(
            entity_id=request.entity_id,
            requirement_id=request.requirement_id,
            status=request.status,
            confidence=request.confidence,
            assessor=request.assessor or current_user.id,
        )

        logger.info(
            "compliance_status_updated_via_api",
            entity_id=request.entity_id,
            requirement_id=request.requirement_id,
            status=request.status.value,
            user_id=current_user.id,
        )

        return {
            "success": True,
            "entity_id": request.entity_id,
            "requirement_id": request.requirement_id,
            "status": request.status.value,
        }

    except Exception as e:
        logger.error("compliance_update_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update compliance status: {str(e)}",
        )


@router.get("/status/{entity_id}")
async def get_entity_compliance_status(
    entity_id: str,
) -> dict[str, Any]:
    """
    Get compliance status for all requirements applicable to an entity.

    Returns a dictionary of requirement_id -> status details.
    """
    engine = ComplianceQueryEngine()

    try:
        return await engine.get_entity_compliance_status(entity_id)

    except Exception as e:
        logger.error("compliance_status_failed", entity_id=entity_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get compliance status: {str(e)}",
        )

