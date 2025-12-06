"""
Tier Management Routes
======================

API endpoints for compliance tier assignment and management.

Version: 0.1.0
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.entity_assessment.services.tier import (
    ComplianceTier,
    TierService,
)
from shared.auth import User, get_current_user
from shared.database.postgres import get_postgres_session
from shared.logging import get_logger


logger = get_logger(__name__)

router = APIRouter()

# Initialize tier service
tier_service = TierService()


# =============================================================================
# Request/Response Models
# =============================================================================


class TierCalculationRequest(BaseModel):
    """Request for tier calculation."""

    entity_type: str = Field(..., description="Type of entity")
    size: str | None = Field(None, description="Size category")
    employee_count: int | None = Field(None, description="Number of employees")
    annual_revenue: float | None = Field(None, description="Annual revenue")
    jurisdictions: list[str] = Field(default=[], description="Operating jurisdictions")
    sectors: list[str] = Field(default=[], description="Business sectors")
    risk_factors: dict[str, bool] = Field(default={}, description="Risk factors")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "entity_type": "corporation",
                    "size": "large",
                    "employee_count": 5000,
                    "annual_revenue": 100000000,
                    "jurisdictions": ["US", "EU"],
                    "sectors": ["FINANCE", "TECHNOLOGY"],
                    "risk_factors": {
                        "processes_personal_data": True,
                        "cross_border_transfers": True,
                    },
                }
            ]
        }
    }


class TierOverrideRequest(BaseModel):
    """Request to override entity tier."""

    tier: ComplianceTier = Field(..., description="New tier")
    reason: str = Field(..., min_length=10, description="Reason for override")


class TierCostEstimateRequest(BaseModel):
    """Request for tier cost estimate."""

    tier: ComplianceTier = Field(..., description="Tier to estimate")
    requirement_count: int = Field(..., ge=0, description="Number of requirements")


class TierRecommendationResponse(BaseModel):
    """Response for tier recommendation."""

    recommended_tier: str
    confidence: float
    risk_level: str
    factors: list[dict[str, Any]]
    alternatives: list[dict[str, Any]]
    required_capabilities: list[str]
    upgrade_triggers: list[str]


class TierCostEstimateResponse(BaseModel):
    """Response for tier cost estimate."""

    tier: str
    base_cost: float
    requirement_cost: float
    total_estimate: float
    requirement_count: int
    notes: str


# =============================================================================
# Routes
# =============================================================================


@router.post("/calculate", response_model=TierRecommendationResponse)
async def calculate_tier(
    request: TierCalculationRequest,
) -> TierRecommendationResponse:
    """
    Calculate recommended compliance tier.

    Uses entity characteristics to determine the appropriate tier.
    This endpoint does not require authentication - it's for planning purposes.
    """
    recommendation = tier_service.determine_tier(
        entity_type=request.entity_type,
        size=request.size,
        employee_count=request.employee_count,
        annual_revenue=request.annual_revenue,
        jurisdictions=request.jurisdictions,
        sectors=request.sectors,
        risk_factors=request.risk_factors,
    )

    logger.info(
        "tier_calculated",
        recommended=recommendation.recommended_tier.value,
        confidence=recommendation.confidence,
    )

    return TierRecommendationResponse(
        recommended_tier=recommendation.recommended_tier.value,
        confidence=recommendation.confidence,
        risk_level=recommendation.risk_level.value,
        factors=recommendation.factors,
        alternatives=recommendation.alternatives,
        required_capabilities=recommendation.required_capabilities,
        upgrade_triggers=recommendation.upgrade_triggers,
    )


@router.get("/entity/{entity_id}", response_model=TierRecommendationResponse)
async def get_entity_tier_recommendation(
    entity_id: str,
    db: AsyncSession = Depends(get_postgres_session),
) -> TierRecommendationResponse:
    """
    Get tier recommendation for an existing entity.

    Fetches entity data and calculates the recommended tier.
    """
    # Get entity data
    query = text("""
        SELECT 
            entity_type, size, employee_count, annual_revenue,
            jurisdictions, sectors, metadata
        FROM core.entities
        WHERE id = :entity_id AND deleted_at IS NULL
    """)

    result = await db.execute(query, {"entity_id": entity_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        )

    # Calculate tier
    recommendation = tier_service.determine_tier(
        entity_type=row.entity_type,
        size=row.size,
        employee_count=row.employee_count,
        annual_revenue=float(row.annual_revenue) if row.annual_revenue else None,
        jurisdictions=row.jurisdictions or [],
        sectors=row.sectors or [],
        risk_factors=row.metadata.get("risk_factors", {}) if row.metadata else {},
    )

    return TierRecommendationResponse(
        recommended_tier=recommendation.recommended_tier.value,
        confidence=recommendation.confidence,
        risk_level=recommendation.risk_level.value,
        factors=recommendation.factors,
        alternatives=recommendation.alternatives,
        required_capabilities=recommendation.required_capabilities,
        upgrade_triggers=recommendation.upgrade_triggers,
    )


@router.put("/entity/{entity_id}", response_model=dict[str, Any])
async def update_entity_tier(
    entity_id: str,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Recalculate and update entity's tier.

    Requires authentication.
    """
    # Get entity data
    query = text("""
        SELECT 
            entity_type, size, employee_count, annual_revenue,
            jurisdictions, sectors, metadata, compliance_tier, tier_override
        FROM core.entities
        WHERE id = :entity_id AND deleted_at IS NULL
    """)

    result = await db.execute(query, {"entity_id": entity_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        )

    # Don't recalculate if manually overridden
    if row.tier_override:
        return {
            "entity_id": entity_id,
            "tier": row.compliance_tier,
            "tier_override": True,
            "message": "Tier is manually overridden",
        }

    # Calculate new tier
    recommendation = tier_service.determine_tier(
        entity_type=row.entity_type,
        size=row.size,
        employee_count=row.employee_count,
        annual_revenue=float(row.annual_revenue) if row.annual_revenue else None,
        jurisdictions=row.jurisdictions or [],
        sectors=row.sectors or [],
        risk_factors=row.metadata.get("risk_factors", {}) if row.metadata else {},
    )

    # Update entity
    update_query = text("""
        UPDATE core.entities
        SET compliance_tier = :tier, updated_at = NOW()
        WHERE id = :entity_id
    """)

    await db.execute(
        update_query,
        {
            "entity_id": entity_id,
            "tier": recommendation.recommended_tier.value,
        },
    )

    logger.info(
        "entity_tier_updated",
        entity_id=entity_id,
        old_tier=row.compliance_tier,
        new_tier=recommendation.recommended_tier.value,
        user_id=current_user.id,
    )

    return {
        "entity_id": entity_id,
        "previous_tier": row.compliance_tier,
        "new_tier": recommendation.recommended_tier.value,
        "confidence": recommendation.confidence,
        "risk_level": recommendation.risk_level.value,
    }


@router.post("/entity/{entity_id}/override", response_model=dict[str, Any])
async def override_entity_tier(
    entity_id: str,
    request: TierOverrideRequest,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Manually override entity's tier.

    Requires authentication. The override persists until cleared.
    """
    # Check entity exists
    check_query = text("""
        SELECT compliance_tier FROM core.entities
        WHERE id = :entity_id AND deleted_at IS NULL
    """)

    result = await db.execute(check_query, {"entity_id": entity_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        )

    # Update with override
    update_query = text("""
        UPDATE core.entities
        SET compliance_tier = :tier,
            tier_override = true,
            tier_override_reason = :reason,
            updated_at = NOW(),
            updated_by = :user_id
        WHERE id = :entity_id
    """)

    await db.execute(
        update_query,
        {
            "entity_id": entity_id,
            "tier": request.tier.value,
            "reason": request.reason,
            "user_id": current_user.id,
        },
    )

    logger.info(
        "entity_tier_overridden",
        entity_id=entity_id,
        old_tier=row.compliance_tier,
        new_tier=request.tier.value,
        reason=request.reason,
        user_id=current_user.id,
    )

    return {
        "entity_id": entity_id,
        "previous_tier": row.compliance_tier,
        "new_tier": request.tier.value,
        "tier_override": True,
        "override_reason": request.reason,
    }


@router.delete("/entity/{entity_id}/override", response_model=dict[str, Any])
async def clear_tier_override(
    entity_id: str,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Clear tier override and recalculate.

    Requires authentication.
    """
    # Get entity data
    query = text("""
        SELECT 
            entity_type, size, employee_count, annual_revenue,
            jurisdictions, sectors, metadata, compliance_tier
        FROM core.entities
        WHERE id = :entity_id AND deleted_at IS NULL
    """)

    result = await db.execute(query, {"entity_id": entity_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        )

    # Calculate natural tier
    recommendation = tier_service.determine_tier(
        entity_type=row.entity_type,
        size=row.size,
        employee_count=row.employee_count,
        annual_revenue=float(row.annual_revenue) if row.annual_revenue else None,
        jurisdictions=row.jurisdictions or [],
        sectors=row.sectors or [],
        risk_factors=row.metadata.get("risk_factors", {}) if row.metadata else {},
    )

    # Clear override and set natural tier
    update_query = text("""
        UPDATE core.entities
        SET compliance_tier = :tier,
            tier_override = false,
            tier_override_reason = NULL,
            updated_at = NOW(),
            updated_by = :user_id
        WHERE id = :entity_id
    """)

    await db.execute(
        update_query,
        {
            "entity_id": entity_id,
            "tier": recommendation.recommended_tier.value,
            "user_id": current_user.id,
        },
    )

    logger.info(
        "entity_tier_override_cleared",
        entity_id=entity_id,
        previous_tier=row.compliance_tier,
        new_tier=recommendation.recommended_tier.value,
        user_id=current_user.id,
    )

    return {
        "entity_id": entity_id,
        "previous_tier": row.compliance_tier,
        "new_tier": recommendation.recommended_tier.value,
        "tier_override": False,
    }


@router.post("/cost-estimate", response_model=TierCostEstimateResponse)
async def estimate_tier_cost(
    request: TierCostEstimateRequest,
) -> TierCostEstimateResponse:
    """
    Estimate compliance cost for a tier.

    Provides a rough estimate based on tier and requirement count.
    """
    estimate = tier_service.calculate_tier_cost_estimate(
        tier=request.tier,
        requirement_count=request.requirement_count,
    )

    return TierCostEstimateResponse(**estimate)


@router.get("/requirements/{tier}", response_model=dict[str, Any])
async def get_tier_requirements(
    tier: ComplianceTier,
) -> dict[str, Any]:
    """
    Get requirements and capabilities for a tier.

    Returns what's needed to operate at a given tier.
    """
    capabilities = {
        ComplianceTier.BASIC: {
            "assessment_frequency": "Annual",
            "evidence_requirements": "Self-attestation",
            "monitoring": "None",
            "capabilities": [
                "Self-attestation support",
                "Basic document management",
                "Annual assessment cycle",
            ],
            "expected_controls": [
                "Basic policies in place",
                "Documented procedures",
                "Employee acknowledgment",
            ],
        },
        ComplianceTier.STANDARD: {
            "assessment_frequency": "Quarterly",
            "evidence_requirements": "Document review",
            "monitoring": "Periodic",
            "capabilities": [
                "Document review workflows",
                "Quarterly assessment cycle",
                "Evidence management",
                "Multi-jurisdiction tracking",
                "Risk scoring",
            ],
            "expected_controls": [
                "Formal compliance program",
                "Dedicated compliance function",
                "Regular training",
                "Internal audits",
            ],
        },
        ComplianceTier.ADVANCED: {
            "assessment_frequency": "Continuous",
            "evidence_requirements": "Automated + cryptographic",
            "monitoring": "Real-time",
            "capabilities": [
                "Continuous monitoring",
                "Real-time compliance tracking",
                "Automated evidence collection",
                "Third-party audit support",
                "Zero-knowledge proofs",
                "Cryptographic attestations",
                "Advanced analytics",
            ],
            "expected_controls": [
                "Chief Compliance Officer",
                "Dedicated compliance team",
                "Real-time monitoring systems",
                "External audit program",
                "Board-level reporting",
            ],
        },
    }

    tier_info = capabilities.get(tier, {})

    return {
        "tier": tier.value,
        **tier_info,
    }
