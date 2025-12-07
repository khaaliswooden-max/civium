"""
Visitor Management API Endpoints.

CRUD operations for visitor records and pre-registration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field


router = APIRouter(prefix="/visitors", tags=["visitors"])


# In-memory store for development
_visitors: dict[str, dict[str, Any]] = {}


class VisitorCreate(BaseModel):
    """Request to create a new visitor pre-registration."""

    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    purpose: str = Field(..., min_length=5, max_length=500)
    host_employee_id: str = Field(..., description="Employee hosting the visitor")
    expected_arrival: datetime
    expected_departure: datetime | None = None
    requires_escort: bool = False
    special_requirements: list[str] = Field(default_factory=list)


class VisitorResponse(BaseModel):
    """Visitor record response."""

    id: str
    full_name: str
    email: str
    phone: str | None
    company: str | None
    purpose: str
    host_employee_id: str
    expected_arrival: datetime
    expected_departure: datetime | None
    requires_escort: bool
    special_requirements: list[str]
    status: str
    created_at: datetime
    screening_status: str | None = None
    badge_issued: bool = False


class VisitorUpdate(BaseModel):
    """Request to update visitor information."""

    purpose: str | None = None
    expected_arrival: datetime | None = None
    expected_departure: datetime | None = None
    requires_escort: bool | None = None
    special_requirements: list[str] | None = None


@router.post(
    "/",
    response_model=VisitorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Pre-register a visitor",
)
async def create_visitor(visitor: VisitorCreate) -> VisitorResponse:
    """
    Pre-register a visitor for facility access.

    Creates a visitor record and triggers background screening.
    """
    visitor_id = f"VIS-{uuid4().hex[:8].upper()}"
    now = datetime.utcnow()

    record = {
        "id": visitor_id,
        "full_name": visitor.full_name,
        "email": visitor.email,
        "phone": visitor.phone,
        "company": visitor.company,
        "purpose": visitor.purpose,
        "host_employee_id": visitor.host_employee_id,
        "expected_arrival": visitor.expected_arrival,
        "expected_departure": visitor.expected_departure,
        "requires_escort": visitor.requires_escort,
        "special_requirements": visitor.special_requirements,
        "status": "pending",
        "created_at": now,
        "screening_status": None,
        "badge_issued": False,
    }

    _visitors[visitor_id] = record
    return VisitorResponse(**record)


@router.get(
    "/",
    response_model=list[VisitorResponse],
    summary="List visitors",
)
async def list_visitors(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[VisitorResponse]:
    """List visitors with optional status filter."""
    visitors = list(_visitors.values())

    if status_filter:
        visitors = [v for v in visitors if v["status"] == status_filter]

    return [VisitorResponse(**v) for v in visitors[offset : offset + limit]]


@router.get(
    "/{visitor_id}",
    response_model=VisitorResponse,
    summary="Get visitor by ID",
)
async def get_visitor(visitor_id: str) -> VisitorResponse:
    """Get a specific visitor record."""
    if visitor_id not in _visitors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visitor {visitor_id} not found",
        )
    return VisitorResponse(**_visitors[visitor_id])


@router.patch(
    "/{visitor_id}",
    response_model=VisitorResponse,
    summary="Update visitor",
)
async def update_visitor(visitor_id: str, update: VisitorUpdate) -> VisitorResponse:
    """Update visitor information."""
    if visitor_id not in _visitors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visitor {visitor_id} not found",
        )

    record = _visitors[visitor_id]
    update_data = update.model_dump(exclude_unset=True)
    record.update(update_data)

    return VisitorResponse(**record)


@router.post(
    "/{visitor_id}/check-in",
    response_model=VisitorResponse,
    summary="Check in visitor",
)
async def check_in_visitor(visitor_id: str) -> VisitorResponse:
    """Check in a visitor upon arrival."""
    if visitor_id not in _visitors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visitor {visitor_id} not found",
        )

    record = _visitors[visitor_id]
    if record["status"] == "checked_in":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visitor already checked in",
        )

    record["status"] = "checked_in"
    record["checked_in_at"] = datetime.utcnow()
    record["badge_issued"] = True

    return VisitorResponse(**record)


@router.post(
    "/{visitor_id}/check-out",
    response_model=VisitorResponse,
    summary="Check out visitor",
)
async def check_out_visitor(visitor_id: str) -> VisitorResponse:
    """Check out a visitor upon departure."""
    if visitor_id not in _visitors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visitor {visitor_id} not found",
        )

    record = _visitors[visitor_id]
    record["status"] = "checked_out"
    record["checked_out_at"] = datetime.utcnow()
    record["badge_issued"] = False

    return VisitorResponse(**record)

