"""
SLA Prediction API Endpoints.

Predictive SLA management and breach prevention.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from services.ticket.ml.sla.predictor import SLAPredictionEngine, SLAPrediction


router = APIRouter(prefix="/sla", tags=["sla"])


class SLAPredictionRequest(BaseModel):
    """Request for SLA prediction."""

    id: str = Field(..., description="Ticket ID")
    status: str = Field(default="open")
    priority: str = Field(default="medium")
    sla_target: str | None = Field(None, description="ISO format datetime")
    complexity_score: float = Field(default=0.5, ge=0, le=1)
    updates_count: int = Field(default=0, ge=0)
    reassignment_count: int = Field(default=0, ge=0)
    waiting_on_customer: bool = False


class AgentWorkload(BaseModel):
    """Agent workload metrics."""

    agent_ticket_count: int = Field(default=5, ge=0)
    team_capacity_pct: float = Field(default=0.8, ge=0, le=1)


class SLAPredictionResponse(BaseModel):
    """SLA prediction response."""

    ticket_id: str
    current_status: str
    sla_target: datetime
    time_remaining_hours: float
    breach_probability: float
    risk_level: str
    contributing_factors: list[dict[str, Any]]
    recommended_actions: list[str]
    escalation_recommended: bool

    @classmethod
    def from_prediction(cls, pred: SLAPrediction) -> SLAPredictionResponse:
        """Create response from SLAPrediction."""
        return cls(
            ticket_id=pred.ticket_id,
            current_status=pred.current_status,
            sla_target=pred.sla_target,
            time_remaining_hours=pred.time_remaining.total_seconds() / 3600,
            breach_probability=pred.breach_probability,
            risk_level=pred.risk_level,
            contributing_factors=pred.contributing_factors,
            recommended_actions=pred.recommended_actions,
            escalation_recommended=pred.escalation_recommended,
        )


@router.post(
    "/predict",
    response_model=SLAPredictionResponse,
    summary="Predict SLA breach probability",
)
async def predict_sla_breach(
    ticket: SLAPredictionRequest,
    workload: AgentWorkload | None = None,
) -> SLAPredictionResponse:
    """
    Predict SLA breach probability for a ticket.

    Returns risk assessment with contributing factors
    and recommended actions to prevent breach.
    """
    engine = SLAPredictionEngine()

    ticket_data = {
        "id": ticket.id,
        "status": ticket.status,
        "priority": ticket.priority,
        "sla_target": ticket.sla_target,
        "complexity_score": ticket.complexity_score,
        "updates_count": ticket.updates_count,
        "reassignment_count": ticket.reassignment_count,
        "waiting_on_customer": ticket.waiting_on_customer,
    }

    workload_data = workload.model_dump() if workload else {}

    prediction = engine.predict_breach(ticket_data, workload_data)
    return SLAPredictionResponse.from_prediction(prediction)


@router.get(
    "/at-risk",
    response_model=list[dict[str, Any]],
    summary="Get tickets at risk of SLA breach",
)
async def get_at_risk_tickets(
    threshold: float = Query(0.5, ge=0, le=1, description="Breach probability threshold"),
) -> list[dict[str, Any]]:
    """
    Get tickets at risk of SLA breach.

    Returns tickets with breach probability above threshold.
    """
    # Mock implementation - in production, queries ticket database
    return [
        {
            "ticket_id": "TKT-MOCK001",
            "breach_probability": 0.75,
            "risk_level": "high",
            "time_remaining_hours": 2.5,
        },
        {
            "ticket_id": "TKT-MOCK002",
            "breach_probability": 0.55,
            "risk_level": "medium",
            "time_remaining_hours": 5.0,
        },
    ]


@router.get(
    "/metrics",
    response_model=dict[str, Any],
    summary="Get SLA metrics",
)
async def get_sla_metrics() -> dict[str, Any]:
    """Get current SLA compliance metrics."""
    return {
        "total_tickets": 150,
        "on_track": 120,
        "at_risk": 25,
        "breached": 5,
        "compliance_rate": 0.967,
        "average_resolution_hours": 18.5,
        "by_priority": {
            "critical": {"total": 10, "breached": 1, "compliance": 0.90},
            "high": {"total": 30, "breached": 2, "compliance": 0.93},
            "medium": {"total": 60, "breached": 2, "compliance": 0.97},
            "low": {"total": 50, "breached": 0, "compliance": 1.0},
        },
    }

