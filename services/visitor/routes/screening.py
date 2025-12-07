"""
Visitor Screening API Endpoints.

Provides threat assessment and watchlist screening endpoints
for comprehensive visitor vetting.
"""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.visitor.ml.threat_assessment.engine import (
    ScreeningResult,
    ThreatAssessmentConfig,
    ThreatAssessmentEngine,
    ThreatLevel,
)


router = APIRouter(prefix="/screening", tags=["screening"])


class VisitorScreeningRequest(BaseModel):
    """Request body for visitor screening."""

    visitor_data: dict[str, Any] = Field(
        ...,
        description="Visitor information including name, DOB, purpose",
        json_schema_extra={
            "example": {
                "id": "VIS-12345",
                "full_name": "John Doe",
                "date_of_birth": "1985-03-15",
                "purpose": "meeting",
            }
        },
    )
    id_document: str = Field(
        ...,
        description="Base64 encoded government ID image",
    )
    selfie: str = Field(
        ...,
        description="Base64 encoded live photo for face matching",
    )


class ScreeningResponse(BaseModel):
    """Response from visitor screening."""

    visitor_id: str
    threat_level: str
    confidence: float
    identity_verification: dict[str, Any]
    watchlist_hits: list[dict[str, Any]]
    behavioral_flags: list[dict[str, Any]]
    recommended_action: str
    requires_escort: bool
    restricted_areas: list[str]

    @classmethod
    def from_result(cls, result: ScreeningResult) -> ScreeningResponse:
        """Create response from ScreeningResult."""
        return cls(
            visitor_id=result.visitor_id,
            threat_level=result.threat_level.value,
            confidence=result.confidence,
            identity_verification=result.identity_verification,
            watchlist_hits=result.watchlist_hits,
            behavioral_flags=result.behavioral_flags,
            recommended_action=result.recommended_action,
            requires_escort=result.requires_escort,
            restricted_areas=result.restricted_areas,
        )


@router.post(
    "/screen",
    response_model=ScreeningResponse,
    status_code=status.HTTP_200_OK,
    summary="Screen visitor for security threats",
    description="Performs comprehensive visitor screening including identity "
                "verification, watchlist checks, and behavioral analysis.",
)
async def screen_visitor(request: VisitorScreeningRequest) -> ScreeningResponse:
    """
    Screen a visitor for security threats.

    This endpoint performs:
    1. Identity verification (ID document + selfie matching)
    2. Watchlist screening (OFAC SDN, SAM exclusions, internal)
    3. Behavioral analysis (visit history, previous denials)
    4. Risk aggregation and threat level determination

    Returns screening result with recommended actions.
    """
    try:
        # Decode base64 images
        id_document = base64.b64decode(request.id_document)
        selfie = base64.b64decode(request.selfie)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 image data: {e!s}",
        ) from e

    # Ensure visitor data has required fields
    visitor_data = request.visitor_data
    if "id" not in visitor_data:
        visitor_data["id"] = f"VIS-{hash(visitor_data.get('full_name', ''))}"
    if "full_name" not in visitor_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="visitor_data must include 'full_name'",
        )

    config = ThreatAssessmentConfig()
    async with ThreatAssessmentEngine(config) as engine:
        result = await engine.screen_visitor(visitor_data, id_document, selfie)

    return ScreeningResponse.from_result(result)


@router.get(
    "/threat-levels",
    response_model=list[dict[str, str]],
    summary="Get available threat levels",
)
async def get_threat_levels() -> list[dict[str, str]]:
    """Get list of available threat levels with descriptions."""
    return [
        {"level": ThreatLevel.CLEAR.value, "description": "No threats detected, approved for entry"},
        {"level": ThreatLevel.REVIEW.value, "description": "Additional verification recommended"},
        {"level": ThreatLevel.ESCALATE.value, "description": "Security review required before entry"},
        {"level": ThreatLevel.DENY.value, "description": "Entry denied, security escalation required"},
    ]

