"""
Compliance Models
=================

Models for compliance states, events, and scores.

Version: 0.1.0
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ComplianceStatus(str, Enum):
    """Compliance status for a requirement."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_ASSESSED = "not_assessed"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"


class EventSeverity(str, Enum):
    """Severity levels for compliance events."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ComplianceState(BaseModel):
    """Compliance state for an entity-requirement pair."""

    id: str = Field(default="", description="State ID")
    entity_id: str
    requirement_id: str
    status: ComplianceStatus

    # Verification
    verification_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    evidence_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of evidence",
    )
    verified_by: str | None = None

    # Next review
    next_review: datetime | None = None

    # Metadata
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceEvent(BaseModel):
    """A compliance-related event."""

    id: str = Field(default="", description="Event ID")
    entity_id: str
    assessment_id: str | None = None
    requirement_id: str | None = None

    # Event details
    event_type: str = Field(
        ...,
        description="Event type (score_change, tier_upgrade, violation, etc.)",
    )
    event_data: dict[str, Any] = Field(default_factory=dict)

    # Severity
    severity: EventSeverity = EventSeverity.INFO

    # Timestamp
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Processing
    processed: bool = False
    processed_at: datetime | None = None


class ComplianceGap(BaseModel):
    """A compliance gap (requirement without compliant state)."""

    entity_id: str
    requirement_id: str
    requirement_text: str | None = None
    regulation_id: str | None = None
    regulation_name: str | None = None

    # Gap details
    current_status: ComplianceStatus = ComplianceStatus.NOT_ASSESSED
    priority: str = Field(default="medium", description="low, medium, high, critical")
    estimated_effort: str | None = Field(
        default=None,
        description="Estimated effort to close gap",
    )

    # Deadline
    deadline: datetime | None = None

    # Recommendations
    recommendations: list[str] = Field(default_factory=list)


class ComplianceScore(BaseModel):
    """Compliance score breakdown."""

    entity_id: str

    # Overall score
    overall_score: float = Field(..., ge=0, le=5)
    overall_percentage: float = Field(..., ge=0, le=100)

    # Breakdown by tier
    tier_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Score by compliance tier",
    )

    # Breakdown by regulation
    regulation_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Score by regulation",
    )

    # Statistics
    total_requirements: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    partial_count: int = 0
    not_assessed_count: int = 0

    # Timestamp
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def compliance_rate(self) -> float:
        """Calculate compliance rate."""
        assessed = self.compliant_count + self.non_compliant_count + self.partial_count
        if assessed == 0:
            return 0.0
        # Partial compliance counts as 0.5
        compliant = self.compliant_count + (self.partial_count * 0.5)
        return (compliant / assessed) * 100


class ComplianceSummary(BaseModel):
    """High-level compliance summary for an entity."""

    entity_id: str
    entity_name: str

    # Current status
    compliance_tier: str
    compliance_score: float | None
    risk_score: float | None

    # Gap analysis
    total_gaps: int = 0
    critical_gaps: int = 0
    high_priority_gaps: int = 0

    # Assessment status
    last_assessment_date: datetime | None = None
    next_assessment_due: datetime | None = None
    assessments_in_progress: int = 0

    # Trends
    score_trend: str = Field(
        default="stable",
        description="improving, stable, declining",
    )
    score_change_30d: float | None = None

