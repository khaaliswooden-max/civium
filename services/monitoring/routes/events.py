"""
Event Routes
============

API endpoints for compliance event management.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from shared.database.kafka import KafkaClient
from shared.logging import get_logger


logger = get_logger(__name__)
router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class ComplianceEvent(BaseModel):
    """A compliance event."""

    event_id: str
    event_type: str
    entity_id: str
    timestamp: datetime
    data: dict[str, Any]
    severity: str = "info"
    source: str = "unknown"


class PublishEventRequest(BaseModel):
    """Request to publish a compliance event."""

    event_type: str = Field(..., description="Event type identifier")
    entity_id: str = Field(..., description="Entity this event relates to")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload")
    severity: str = Field("info", pattern="^(debug|info|warning|error|critical)$")
    source: str = Field("api", description="Event source identifier")


class PublishEventResponse(BaseModel):
    """Response from publishing an event."""

    success: bool
    event_id: str
    topic: str
    partition: int | None = None
    offset: int | None = None


class EventListResponse(BaseModel):
    """Response containing list of events."""

    events: list[ComplianceEvent]
    total: int
    has_more: bool


# ============================================================================
# Event Types
# ============================================================================


EVENT_TOPICS = {
    "assessment.started": "civium.compliance.assessments",
    "assessment.completed": "civium.compliance.assessments",
    "score.calculated": "civium.compliance.scores",
    "tier.changed": "civium.compliance.tiers",
    "violation.detected": "civium.compliance.violations",
    "requirement.met": "civium.compliance.requirements",
    "regulation.updated": "civium.regulations.updates",
    "proof.generated": "civium.verification.proofs",
    "credential.issued": "civium.verification.credentials",
    "entity.created": "civium.entities.changes",
    "entity.updated": "civium.entities.changes",
}


# ============================================================================
# Event Endpoints
# ============================================================================


@router.post("/publish", response_model=PublishEventResponse)
async def publish_event(request: PublishEventRequest) -> PublishEventResponse:
    """
    Publish a compliance event.

    Events are published to Kafka topics based on event type.
    This enables real-time processing by downstream consumers.

    Args:
        request: Event publication request

    Returns:
        PublishEventResponse with publication details
    """
    event_id = str(uuid4())

    logger.info(
        "publishing_event",
        event_id=event_id,
        event_type=request.event_type,
        entity_id=request.entity_id,
    )

    # Determine topic
    topic = EVENT_TOPICS.get(
        request.event_type,
        "civium.compliance.events",  # Default topic
    )

    # Build event
    event = ComplianceEvent(
        event_id=event_id,
        event_type=request.event_type,
        entity_id=request.entity_id,
        timestamp=datetime.utcnow(),
        data=request.data,
        severity=request.severity,
        source=request.source,
    )

    # Publish to Kafka
    try:
        result = await KafkaClient.publish(
            topic=topic,
            key=request.entity_id,
            value=event.model_dump_json(),
        )

        return PublishEventResponse(
            success=True,
            event_id=event_id,
            topic=topic,
            partition=result.get("partition"),
            offset=result.get("offset"),
        )

    except Exception as e:
        logger.error("event_publish_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to publish event",
        ) from e


@router.get("/entity/{entity_id}", response_model=EventListResponse)
async def get_entity_events(
    entity_id: str,
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> EventListResponse:
    """
    Get events for a specific entity.

    Args:
        entity_id: Entity identifier
        event_type: Optional filter by event type
        severity: Optional filter by severity
        limit: Maximum events to return
        offset: Number of events to skip

    Returns:
        EventListResponse with list of events
    """
    logger.info(
        "get_entity_events",
        entity_id=entity_id,
        event_type=event_type,
        limit=limit,
    )

    # TODO: Implement event storage and retrieval
    # Events would typically be stored in InfluxDB or a similar time-series DB
    return EventListResponse(
        events=[],
        total=0,
        has_more=False,
    )


@router.get("/recent", response_model=EventListResponse)
async def get_recent_events(
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
) -> EventListResponse:
    """
    Get recent events across all entities.

    Args:
        event_type: Optional filter by event type
        severity: Optional filter by severity
        limit: Maximum events to return

    Returns:
        EventListResponse with recent events
    """
    logger.info(
        "get_recent_events",
        event_type=event_type,
        limit=limit,
    )

    # TODO: Implement event retrieval from storage
    return EventListResponse(
        events=[],
        total=0,
        has_more=False,
    )


@router.get("/types")
async def get_event_types() -> dict[str, Any]:
    """
    Get available event types and their topics.

    Returns:
        Dictionary of event types and associated Kafka topics
    """
    return {
        "event_types": EVENT_TOPICS,
        "default_topic": "civium.compliance.events",
    }
