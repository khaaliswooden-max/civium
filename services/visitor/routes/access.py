"""
Access Control API Endpoints.

Zone-based access control and escort management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field


router = APIRouter(prefix="/access", tags=["access"])


# Access zones configuration
ACCESS_ZONES = {
    "lobby": {"level": 0, "escort_required": False},
    "general_office": {"level": 1, "escort_required": False},
    "conference_rooms": {"level": 1, "escort_required": False},
    "secure_areas": {"level": 2, "escort_required": True},
    "executive_floor": {"level": 3, "escort_required": True},
    "data_center": {"level": 4, "escort_required": True},
    "scif": {"level": 5, "escort_required": True, "special_clearance": True},
}

# In-memory access log
_access_log: list[dict[str, Any]] = []


class AccessRequest(BaseModel):
    """Request for zone access."""

    visitor_id: str
    zone: str = Field(..., description="Target access zone")
    escort_id: str | None = Field(None, description="Escort employee ID if required")


class AccessResponse(BaseModel):
    """Access decision response."""

    access_id: str
    visitor_id: str
    zone: str
    granted: bool
    reason: str
    escort_required: bool
    escort_id: str | None
    valid_until: datetime | None
    restrictions: list[str]


class AccessLogEntry(BaseModel):
    """Access log entry."""

    id: str
    visitor_id: str
    zone: str
    action: str  # entry, exit, denied
    timestamp: datetime
    escort_id: str | None
    notes: str | None


@router.post(
    "/request",
    response_model=AccessResponse,
    summary="Request zone access",
)
async def request_access(request: AccessRequest) -> AccessResponse:
    """
    Request access to a specific zone.

    Evaluates visitor clearance level, escort requirements,
    and zone restrictions to make access decision.
    """
    if request.zone not in ACCESS_ZONES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown zone: {request.zone}. Valid zones: {list(ACCESS_ZONES.keys())}",
        )

    zone_config = ACCESS_ZONES[request.zone]
    access_id = f"ACC-{uuid4().hex[:8].upper()}"

    # Check escort requirement
    escort_required = zone_config.get("escort_required", False)
    if escort_required and not request.escort_id:
        return AccessResponse(
            access_id=access_id,
            visitor_id=request.visitor_id,
            zone=request.zone,
            granted=False,
            reason=f"Zone '{request.zone}' requires escort",
            escort_required=True,
            escort_id=None,
            valid_until=None,
            restrictions=["escort_required"],
        )

    # Check special clearance
    if zone_config.get("special_clearance"):
        return AccessResponse(
            access_id=access_id,
            visitor_id=request.visitor_id,
            zone=request.zone,
            granted=False,
            reason="Special clearance required for SCIF access",
            escort_required=True,
            escort_id=request.escort_id,
            valid_until=None,
            restrictions=["special_clearance_required"],
        )

    # Grant access
    now = datetime.utcnow()
    valid_hours = 8 if zone_config["level"] <= 1 else 4

    # Log the access
    log_entry = {
        "id": f"LOG-{uuid4().hex[:8].upper()}",
        "visitor_id": request.visitor_id,
        "zone": request.zone,
        "action": "entry",
        "timestamp": now,
        "escort_id": request.escort_id,
        "notes": None,
    }
    _access_log.append(log_entry)

    return AccessResponse(
        access_id=access_id,
        visitor_id=request.visitor_id,
        zone=request.zone,
        granted=True,
        reason="Access granted",
        escort_required=escort_required,
        escort_id=request.escort_id,
        valid_until=datetime(
            now.year, now.month, now.day, now.hour + valid_hours, now.minute
        ) if now.hour + valid_hours < 24 else None,
        restrictions=[],
    )


@router.get(
    "/zones",
    response_model=dict[str, Any],
    summary="Get available zones",
)
async def get_zones() -> dict[str, Any]:
    """Get list of access zones and their requirements."""
    return ACCESS_ZONES


@router.get(
    "/log",
    response_model=list[AccessLogEntry],
    summary="Get access log",
)
async def get_access_log(
    visitor_id: str | None = Query(None),
    zone: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[AccessLogEntry]:
    """Get access log entries with optional filters."""
    entries = _access_log.copy()

    if visitor_id:
        entries = [e for e in entries if e["visitor_id"] == visitor_id]
    if zone:
        entries = [e for e in entries if e["zone"] == zone]

    return [AccessLogEntry(**e) for e in entries[-limit:]]


@router.post(
    "/log/{visitor_id}/exit",
    response_model=AccessLogEntry,
    summary="Log zone exit",
)
async def log_exit(visitor_id: str, zone: str) -> AccessLogEntry:
    """Log visitor exit from a zone."""
    log_entry = {
        "id": f"LOG-{uuid4().hex[:8].upper()}",
        "visitor_id": visitor_id,
        "zone": zone,
        "action": "exit",
        "timestamp": datetime.utcnow(),
        "escort_id": None,
        "notes": None,
    }
    _access_log.append(log_entry)
    return AccessLogEntry(**log_entry)

