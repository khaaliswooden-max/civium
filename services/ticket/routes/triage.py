"""
Ticket Triage API Endpoints.

AI-powered ticket classification and routing.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.ticket.ml.triage.classifier import TicketTriageEngine, TriageResult


router = APIRouter(prefix="/triage", tags=["triage"])


class TriageRequest(BaseModel):
    """Request for ticket triage."""

    id: str = Field(..., description="Ticket ID")
    subject: str = Field(..., description="Ticket subject")
    description: str = Field(..., description="Ticket description")
    requester_id: str | None = None
    requester_vip: bool = False
    users_affected: int = 1


class TriageResponse(BaseModel):
    """Triage result response."""

    ticket_id: str
    category: str
    subcategory: str
    priority: str
    sentiment: str
    assigned_team: str
    assigned_agent: str | None
    confidence: float
    suggested_solutions: list[dict[str, Any]]
    estimated_resolution_time: int

    @classmethod
    def from_result(cls, result: TriageResult) -> TriageResponse:
        """Create response from TriageResult."""
        return cls(
            ticket_id=result.ticket_id,
            category=result.category,
            subcategory=result.subcategory,
            priority=result.priority,
            sentiment=result.sentiment,
            assigned_team=result.assigned_team,
            assigned_agent=result.assigned_agent,
            confidence=result.confidence,
            suggested_solutions=result.suggested_solutions,
            estimated_resolution_time=result.estimated_resolution_time,
        )


@router.post(
    "/analyze",
    response_model=TriageResponse,
    summary="Triage a ticket",
    description="Analyze ticket and return classification, priority, and routing.",
)
async def triage_ticket(request: TriageRequest) -> TriageResponse:
    """
    Perform AI-powered ticket triage.

    Analyzes ticket content to determine:
    - Category and subcategory
    - Priority level
    - Sentiment
    - Team assignment
    - Suggested solutions from knowledge base
    """
    engine = TicketTriageEngine()

    ticket_data = {
        "id": request.id,
        "subject": request.subject,
        "description": request.description,
        "requester_id": request.requester_id,
        "requester_vip": request.requester_vip,
        "users_affected": request.users_affected,
    }

    result = engine.triage_ticket(ticket_data)
    return TriageResponse.from_result(result)


@router.get(
    "/categories",
    response_model=list[str],
    summary="Get available categories",
)
async def get_categories() -> list[str]:
    """Get list of ticket categories."""
    return TicketTriageEngine.CATEGORIES


@router.get(
    "/priorities",
    response_model=list[str],
    summary="Get priority levels",
)
async def get_priorities() -> list[str]:
    """Get list of priority levels."""
    return TicketTriageEngine.PRIORITIES


@router.get(
    "/teams",
    response_model=dict[str, str],
    summary="Get team routing map",
)
async def get_team_routing() -> dict[str, str]:
    """Get category to team routing map."""
    return TicketTriageEngine.TEAM_ROUTING

