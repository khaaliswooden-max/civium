"""
Ticket Management API Endpoints.

CRUD operations for service tickets.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field


router = APIRouter(prefix="/tickets", tags=["tickets"])


# In-memory store for development
_tickets: dict[str, dict[str, Any]] = {}


class TicketCreate(BaseModel):
    """Request to create a new ticket."""

    subject: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    requester_id: str
    requester_email: str
    requester_vip: bool = False
    category: str | None = None
    priority: str | None = None
    users_affected: int = 1


class TicketResponse(BaseModel):
    """Ticket response model."""

    id: str
    subject: str
    description: str
    requester_id: str
    requester_email: str
    requester_vip: bool
    category: str | None
    subcategory: str | None
    priority: str
    status: str
    assigned_team: str | None
    assigned_agent: str | None
    created_at: datetime
    updated_at: datetime
    sla_target: datetime
    users_affected: int


class TicketUpdate(BaseModel):
    """Request to update ticket."""

    subject: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assigned_agent: str | None = None


@router.post(
    "/",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ticket",
)
async def create_ticket(ticket: TicketCreate) -> TicketResponse:
    """Create a new service ticket."""
    ticket_id = f"TKT-{uuid4().hex[:8].upper()}"
    now = datetime.utcnow()

    # Calculate SLA target based on priority
    sla_hours = {"critical": 4, "high": 8, "medium": 24, "low": 48}
    priority = ticket.priority or "medium"
    sla_target = now + timedelta(hours=sla_hours.get(priority, 24))

    record = {
        "id": ticket_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "requester_id": ticket.requester_id,
        "requester_email": ticket.requester_email,
        "requester_vip": ticket.requester_vip,
        "category": ticket.category,
        "subcategory": None,
        "priority": priority,
        "status": "open",
        "assigned_team": None,
        "assigned_agent": None,
        "created_at": now,
        "updated_at": now,
        "sla_target": sla_target,
        "users_affected": ticket.users_affected,
    }

    _tickets[ticket_id] = record
    return TicketResponse(**record)


@router.get(
    "/",
    response_model=list[TicketResponse],
    summary="List tickets",
)
async def list_tickets(
    status_filter: str | None = Query(None, alias="status"),
    priority: str | None = Query(None),
    assigned_team: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[TicketResponse]:
    """List tickets with optional filters."""
    tickets = list(_tickets.values())

    if status_filter:
        tickets = [t for t in tickets if t["status"] == status_filter]
    if priority:
        tickets = [t for t in tickets if t["priority"] == priority]
    if assigned_team:
        tickets = [t for t in tickets if t["assigned_team"] == assigned_team]

    return [TicketResponse(**t) for t in tickets[offset : offset + limit]]


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket by ID",
)
async def get_ticket(ticket_id: str) -> TicketResponse:
    """Get a specific ticket."""
    if ticket_id not in _tickets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )
    return TicketResponse(**_tickets[ticket_id])


@router.patch(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Update ticket",
)
async def update_ticket(ticket_id: str, update: TicketUpdate) -> TicketResponse:
    """Update ticket information."""
    if ticket_id not in _tickets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    record = _tickets[ticket_id]
    update_data = update.model_dump(exclude_unset=True)
    record.update(update_data)
    record["updated_at"] = datetime.utcnow()

    return TicketResponse(**record)


@router.post(
    "/{ticket_id}/resolve",
    response_model=TicketResponse,
    summary="Resolve ticket",
)
async def resolve_ticket(
    ticket_id: str,
    resolution_notes: str = "",
) -> TicketResponse:
    """Mark ticket as resolved."""
    if ticket_id not in _tickets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    record = _tickets[ticket_id]
    record["status"] = "resolved"
    record["resolved_at"] = datetime.utcnow()
    record["resolution_notes"] = resolution_notes
    record["updated_at"] = datetime.utcnow()

    return TicketResponse(**record)


@router.post(
    "/{ticket_id}/close",
    response_model=TicketResponse,
    summary="Close ticket",
)
async def close_ticket(ticket_id: str) -> TicketResponse:
    """Close a resolved ticket."""
    if ticket_id not in _tickets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    record = _tickets[ticket_id]
    record["status"] = "closed"
    record["closed_at"] = datetime.utcnow()
    record["updated_at"] = datetime.utcnow()

    return TicketResponse(**record)

