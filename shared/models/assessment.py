"""
Assessment Models
=================

Models for compliance assessments.

Version: 0.1.0
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class AssessmentStatus(str, Enum):
    """Assessment workflow status."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class CriterionScore(BaseModel):
    """Score for a single assessment criterion."""

    criterion_id: str = Field(..., description="Requirement or criterion ID")
    score: int = Field(..., ge=0, le=5, description="Score (0-5)")
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence document references",
    )
    notes: str | None = None
    assessor_id: str | None = None
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AssessmentBase(BaseModel):
    """Base assessment fields."""

    entity_id: str = Field(..., description="Entity being assessed")
    assessment_type: str = Field(
        ...,
        description="Type of assessment (annual_review, incident_response, etc.)",
    )
    notes: str | None = None


class AssessmentCreate(AssessmentBase):
    """Request model for creating an assessment."""

    assessor_id: str | None = None


class AssessmentUpdate(BaseModel):
    """Request model for updating an assessment."""

    status: AssessmentStatus | None = None
    overall_score: float | None = Field(default=None, ge=0, le=5)
    criterion_scores: list[CriterionScore] | None = None
    notes: str | None = None
    reviewer_id: str | None = None


class Assessment(AssessmentBase):
    """Full assessment model."""

    id: str = Field(..., description="Unique assessment ID")
    status: AssessmentStatus = AssessmentStatus.DRAFT

    # Scores
    overall_score: float | None = Field(
        default=None,
        ge=0,
        le=5,
        description="Overall compliance score",
    )
    criterion_scores: list[CriterionScore] = Field(default_factory=list)

    # Evidence
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="References to evidence documents",
    )

    # Workflow
    assessor_id: str | None = None
    reviewer_id: str | None = None

    # Timestamps
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Blockchain reference
    audit_tx_hash: str | None = Field(
        default=None,
        description="Blockchain transaction hash for audit trail",
    )

    @property
    def is_complete(self) -> bool:
        """Check if assessment is complete."""
        return self.status in (AssessmentStatus.APPROVED, AssessmentStatus.REJECTED)

    @property
    def is_expired(self) -> bool:
        """Check if assessment has expired."""
        if not self.expires_at:
            return False
        return datetime.now(UTC) > self.expires_at

    class Config:
        from_attributes = True


class AssessmentSummary(BaseModel):
    """Lightweight assessment summary."""

    id: str
    entity_id: str
    assessment_type: str
    status: AssessmentStatus
    overall_score: float | None
    started_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True

