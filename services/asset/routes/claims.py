"""
Claims Processing API Endpoints.

Warranty claim submission and fraud detection.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from services.asset.warranty.registry import BlockchainWarrantyRegistry, ClaimResult
from services.asset.ml.fraud.detector import FraudDetector, FraudResult


router = APIRouter(prefix="/claims", tags=["claims"])


# Shared instances
_registry = BlockchainWarrantyRegistry()
_fraud_detector = FraudDetector()


class ClaimSubmitRequest(BaseModel):
    """Request to submit a warranty claim."""

    warranty_id: str = Field(..., description="Warranty identifier")
    claim_type: str = Field(..., description="Type of claim: repair, replacement, refund")
    issue_description: str = Field(..., min_length=10)
    estimated_cost: float = Field(default=0, ge=0)
    claimant_id: str = Field(..., description="Person submitting the claim")
    documentation: list[str] = Field(default_factory=list, description="Attached document IDs")


class ClaimResponse(BaseModel):
    """Claim processing response."""

    claim_id: str
    warranty_id: str
    status: str
    confidence: float
    fraud_score: float
    reason: str
    recommended_action: str
    submitted_at: datetime

    @classmethod
    def from_result(cls, result: ClaimResult, submitted_at: datetime) -> ClaimResponse:
        """Create response from ClaimResult."""
        return cls(
            claim_id=result.claim_id,
            warranty_id=result.warranty_id,
            status=result.status,
            confidence=result.confidence,
            fraud_score=result.fraud_score,
            reason=result.reason,
            recommended_action=result.recommended_action,
            submitted_at=submitted_at,
        )


class FraudAnalysisResponse(BaseModel):
    """Fraud analysis response."""

    claim_id: str
    fraud_score: float
    confidence: float
    risk_level: str
    contributing_factors: list[dict[str, Any]]
    recommended_action: str
    requires_investigation: bool

    @classmethod
    def from_result(cls, result: FraudResult) -> FraudAnalysisResponse:
        """Create response from FraudResult."""
        return cls(
            claim_id=result.claim_id,
            fraud_score=result.fraud_score,
            confidence=result.confidence,
            risk_level=result.risk_level,
            contributing_factors=result.contributing_factors,
            recommended_action=result.recommended_action,
            requires_investigation=result.requires_investigation,
        )


@router.post(
    "/submit",
    response_model=ClaimResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a warranty claim",
)
async def submit_claim(request: ClaimSubmitRequest) -> ClaimResponse:
    """
    Submit a warranty claim for processing.

    The claim is automatically screened for fraud and processed
    according to warranty terms.
    """
    claim_id = f"CLM-{uuid4().hex[:8].upper()}"
    now = datetime.utcnow()

    claim_data = {
        "claim_id": claim_id,
        "claim_type": request.claim_type,
        "issue_description": request.issue_description,
        "estimated_cost": request.estimated_cost,
        "claimant_id": request.claimant_id,
        "documentation": request.documentation,
        "submitted_at": now.isoformat(),
    }

    result = await _registry.process_claim(
        warranty_id=request.warranty_id,
        claim_data=claim_data,
    )

    return ClaimResponse.from_result(result, now)


@router.post(
    "/analyze-fraud",
    response_model=FraudAnalysisResponse,
    summary="Analyze claim for fraud",
)
async def analyze_fraud(request: ClaimSubmitRequest) -> FraudAnalysisResponse:
    """
    Perform fraud analysis on a claim without processing it.

    Useful for pre-screening claims before submission.
    """
    claim_id = f"PREVIEW-{uuid4().hex[:8].upper()}"

    # Get warranty record
    record = await _registry.get_warranty(request.warranty_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warranty {request.warranty_id} not found",
        )

    claim_data = {
        "claim_id": claim_id,
        "claim_type": request.claim_type,
        "issue_description": request.issue_description,
        "estimated_cost": request.estimated_cost,
    }

    # Convert record to dict for fraud detector
    warranty_dict = {
        "warranty_id": record.warranty_id,
        "warranty_end": record.warranty_end.isoformat(),
        "claims_history": record.claims_history,
        "terms": record.terms,
    }

    # Get claimant history
    claimant_history = _fraud_detector.get_claimant_risk_profile(request.claimant_id)

    result = _fraud_detector.detect_fraud(
        claim=claim_data,
        warranty=warranty_dict,
        claimant_history=claimant_history,
    )

    return FraudAnalysisResponse.from_result(result)


@router.get(
    "/{claim_id}",
    response_model=dict[str, Any],
    summary="Get claim status",
)
async def get_claim(claim_id: str) -> dict[str, Any]:
    """Get claim details and current status."""
    # Mock implementation - queries claim database in production
    return {
        "claim_id": claim_id,
        "status": "pending_review",
        "message": "Claim is being reviewed",
    }


@router.get(
    "/warranty/{warranty_id}",
    response_model=list[dict[str, Any]],
    summary="Get claims for warranty",
)
async def get_warranty_claims(
    warranty_id: str,
    limit: int = Query(50, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Get all claims for a warranty."""
    record = await _registry.get_warranty(warranty_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warranty {warranty_id} not found",
        )

    return record.claims_history[-limit:]


@router.get(
    "/claimant/{claimant_id}/profile",
    response_model=dict[str, Any],
    summary="Get claimant risk profile",
)
async def get_claimant_profile(claimant_id: str) -> dict[str, Any]:
    """Get risk profile for a claimant."""
    return _fraud_detector.get_claimant_risk_profile(claimant_id)

