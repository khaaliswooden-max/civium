"""
Assessment Database Models
==========================

SQLAlchemy ORM models for compliance assessments.

Version: 0.1.0
"""

from datetime import datetime
from enum import Enum
from typing import Any
import uuid

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    JSON,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from shared.database.postgres import Base


class AssessmentStatus(str, Enum):
    """Assessment workflow status."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class AssessmentType(str, Enum):
    """Types of assessments."""

    INITIAL = "initial"  # First assessment
    PERIODIC = "periodic"  # Regular scheduled
    TRIGGERED = "triggered"  # Event-triggered
    REMEDIATION = "remediation"  # Following non-compliance
    AUDIT = "audit"  # External audit
    SELF_ASSESSMENT = "self_assessment"


class ItemStatus(str, Enum):
    """Individual item compliance status."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"
    REMEDIATION = "remediation"


class AssessmentModel(Base):
    """
    SQLAlchemy model for compliance assessments.

    An assessment is a point-in-time evaluation of an entity's compliance
    with applicable requirements.
    """

    __tablename__ = "assessments"
    __table_args__ = (
        Index("ix_assessments_entity", "entity_id"),
        Index("ix_assessments_status", "status"),
        Index("ix_assessments_type", "assessment_type"),
        Index("ix_assessments_date", "assessment_date"),
        CheckConstraint("overall_score >= 0 AND overall_score <= 1", name="check_assessment_score"),
        {"schema": "core"},
    )

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Entity relationship
    entity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.entities.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Assessment info
    assessment_type = Column(SQLEnum(AssessmentType), nullable=False, default=AssessmentType.PERIODIC)
    status = Column(SQLEnum(AssessmentStatus), nullable=False, default=AssessmentStatus.DRAFT)

    # Scope
    jurisdictions = Column(ARRAY(String(10)))  # Which jurisdictions assessed
    sectors = Column(ARRAY(String(50)))  # Which sectors assessed
    regulation_ids = Column(ARRAY(String(50)))  # Specific regulations if targeted

    # Dates
    assessment_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    due_date = Column(DateTime(timezone=True))
    valid_until = Column(DateTime(timezone=True))

    # Results
    overall_score = Column(Numeric(5, 4))  # 0.0000 to 1.0000
    risk_level = Column(String(20))  # low, medium, high, critical

    # Counts
    total_items = Column(Integer, default=0)
    compliant_items = Column(Integer, default=0)
    non_compliant_items = Column(Integer, default=0)
    partial_items = Column(Integer, default=0)
    not_applicable_items = Column(Integer, default=0)
    pending_items = Column(Integer, default=0)

    # People
    assessor_id = Column(UUID(as_uuid=True))  # User who performed assessment
    assessor_name = Column(String(255))
    reviewer_id = Column(UUID(as_uuid=True))  # User who reviewed
    reviewer_name = Column(String(255))
    approver_id = Column(UUID(as_uuid=True))  # User who approved
    approver_name = Column(String(255))

    # Notes and attachments
    summary = Column(Text)
    findings = Column(Text)
    recommendations = Column(Text)
    attachments = Column(JSON, default=list)  # List of attachment metadata

    # Configuration
    methodology = Column(String(100))  # Assessment methodology used
    confidence_level = Column(Numeric(5, 4))  # Confidence in results

    # Metadata
    metadata = Column(JSON, default=dict)

    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))

    # Relationships
    entity = relationship("EntityModel", back_populates="assessments")
    items = relationship("AssessmentItemModel", back_populates="assessment", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Assessment {self.id}: {self.entity_id} ({self.status.value})>"

    @property
    def compliance_rate(self) -> float | None:
        """Calculate compliance rate."""
        applicable = self.total_items - (self.not_applicable_items or 0)
        if applicable == 0:
            return None
        return (self.compliant_items or 0) / applicable

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "entity_id": str(self.entity_id),
            "assessment_type": self.assessment_type.value,
            "status": self.status.value,
            "assessment_date": self.assessment_date.isoformat() if self.assessment_date else None,
            "overall_score": float(self.overall_score) if self.overall_score else None,
            "risk_level": self.risk_level,
            "total_items": self.total_items,
            "compliant_items": self.compliant_items,
            "non_compliant_items": self.non_compliant_items,
            "compliance_rate": self.compliance_rate,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AssessmentItemModel(Base):
    """
    SQLAlchemy model for individual assessment items.

    Each item represents an entity's compliance with a specific requirement.
    """

    __tablename__ = "assessment_items"
    __table_args__ = (
        Index("ix_assessment_items_assessment", "assessment_id"),
        Index("ix_assessment_items_requirement", "requirement_id"),
        Index("ix_assessment_items_status", "status"),
        Index("ix_assessment_items_composite", "assessment_id", "requirement_id"),
        {"schema": "core"},
    )

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Relationships
    assessment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    requirement_id = Column(String(100), nullable=False)  # Reference to requirement
    regulation_id = Column(String(100))  # Reference to regulation

    # Requirement context (cached from graph)
    requirement_text = Column(Text)
    requirement_tier = Column(String(20))
    article_ref = Column(String(100))

    # Assessment result
    status = Column(SQLEnum(ItemStatus), nullable=False, default=ItemStatus.PENDING)
    score = Column(Numeric(5, 4))  # 0 to 1 for partial compliance

    # Evidence
    evidence_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)
    evidence_summary = Column(Text)

    # Assessment details
    assessed_at = Column(DateTime(timezone=True))
    assessed_by = Column(UUID(as_uuid=True))
    assessment_method = Column(String(50))  # self_attestation, document_review, etc.

    # Findings
    finding = Column(Text)
    gap_description = Column(Text)
    risk_impact = Column(String(20))  # low, medium, high, critical
    
    # Remediation
    remediation_required = Column(Boolean, default=False)
    remediation_plan = Column(Text)
    remediation_due_date = Column(DateTime(timezone=True))
    remediation_status = Column(String(50))

    # Notes
    notes = Column(Text)
    internal_notes = Column(Text)  # Not shared with entity

    # Metadata
    metadata = Column(JSON, default=dict)

    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assessment = relationship("AssessmentModel", back_populates="items")

    def __repr__(self) -> str:
        return f"<AssessmentItem {self.id}: {self.requirement_id} ({self.status.value})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "assessment_id": str(self.assessment_id),
            "requirement_id": self.requirement_id,
            "regulation_id": self.regulation_id,
            "requirement_text": self.requirement_text,
            "article_ref": self.article_ref,
            "status": self.status.value,
            "score": float(self.score) if self.score else None,
            "finding": self.finding,
            "gap_description": self.gap_description,
            "risk_impact": self.risk_impact,
            "remediation_required": self.remediation_required,
            "assessed_at": self.assessed_at.isoformat() if self.assessed_at else None,
        }

