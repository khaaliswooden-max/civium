"""
Entity Database Model
=====================

SQLAlchemy ORM model for regulated entities.

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
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from shared.database.postgres import Base


class EntityType(str, Enum):
    """Types of regulated entities."""

    CORPORATION = "corporation"
    SME = "sme"
    STARTUP = "startup"
    GOVERNMENT = "government"
    NON_PROFIT = "non_profit"
    INDIVIDUAL = "individual"
    PARTNERSHIP = "partnership"
    SUBSIDIARY = "subsidiary"


class EntitySize(str, Enum):
    """Entity size categories."""

    MICRO = "micro"  # < 10 employees
    SMALL = "small"  # 10-49 employees
    MEDIUM = "medium"  # 50-249 employees
    LARGE = "large"  # 250+ employees


class ComplianceTier(str, Enum):
    """Compliance complexity tiers."""

    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"


class EntityModel(Base):
    """
    SQLAlchemy model for regulated entities.

    Stores all information about organizations subject to compliance requirements.
    """

    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_jurisdiction", "primary_jurisdiction"),
        Index("ix_entities_tier", "compliance_tier"),
        Index("ix_entities_type", "entity_type"),
        Index("ix_entities_created", "created_at"),
        Index("ix_entities_name_search", "name"),  # For ILIKE searches
        CheckConstraint("compliance_score >= 0 AND compliance_score <= 1", name="check_compliance_score"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="check_risk_score"),
        {"schema": "core"},
    )

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic info
    name = Column(String(255), nullable=False, index=True)
    legal_name = Column(String(500))
    entity_type = Column(SQLEnum(EntityType), nullable=False, default=EntityType.CORPORATION)
    size = Column(SQLEnum(EntitySize), default=EntitySize.SMALL)

    # Location and scope
    primary_jurisdiction = Column(String(10), nullable=False)
    jurisdictions = Column(ARRAY(String(10)), default=list)
    sectors = Column(ARRAY(String(50)), default=list)

    # Business details
    employee_count = Column(Integer)
    annual_revenue = Column(Numeric(20, 2))
    founding_date = Column(DateTime(timezone=True))

    # External identifiers
    registration_number = Column(String(100))
    tax_id = Column(String(50))
    lei = Column(String(20))  # Legal Entity Identifier
    did = Column(String(100))  # Decentralized Identifier
    external_id = Column(String(100))  # Customer's own ID

    # Compliance status
    compliance_tier = Column(
        SQLEnum(ComplianceTier),
        nullable=False,
        default=ComplianceTier.BASIC,
    )
    compliance_score = Column(Numeric(5, 4))  # 0.0000 to 1.0000
    risk_score = Column(Numeric(5, 4))  # 0.0000 to 1.0000
    tier_override = Column(Boolean, default=False)  # Manual tier override
    tier_override_reason = Column(Text)

    # Assessment tracking
    last_assessment_id = Column(UUID(as_uuid=True))
    last_assessment_at = Column(DateTime(timezone=True))
    next_assessment_due = Column(DateTime(timezone=True))
    assessment_frequency_days = Column(Integer, default=90)

    # Requirement counts (cached)
    total_requirements = Column(Integer, default=0)
    compliant_requirements = Column(Integer, default=0)
    non_compliant_requirements = Column(Integer, default=0)
    pending_requirements = Column(Integer, default=0)

    # Contact info
    primary_contact_name = Column(String(255))
    primary_contact_email = Column(String(255))
    primary_contact_phone = Column(String(50))

    # Address
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state_province = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(2))  # ISO 3166-1 alpha-2

    # Additional data
    metadata = Column(JSON, default=dict)
    tags = Column(ARRAY(String(50)), default=list)
    notes = Column(Text)

    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    deleted_at = Column(DateTime(timezone=True))  # Soft delete

    # Relationships
    assessments = relationship("AssessmentModel", back_populates="entity", lazy="dynamic")
    evidence = relationship("EvidenceModel", back_populates="entity", lazy="dynamic")
    score_history = relationship("ScoreHistoryModel", back_populates="entity", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Entity {self.id}: {self.name} ({self.compliance_tier.value})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "legal_name": self.legal_name,
            "entity_type": self.entity_type.value,
            "size": self.size.value if self.size else None,
            "primary_jurisdiction": self.primary_jurisdiction,
            "jurisdictions": self.jurisdictions or [],
            "sectors": self.sectors or [],
            "employee_count": self.employee_count,
            "annual_revenue": float(self.annual_revenue) if self.annual_revenue else None,
            "compliance_tier": self.compliance_tier.value,
            "compliance_score": float(self.compliance_score) if self.compliance_score else None,
            "risk_score": float(self.risk_score) if self.risk_score else None,
            "total_requirements": self.total_requirements,
            "compliant_requirements": self.compliant_requirements,
            "last_assessment_at": self.last_assessment_at.isoformat() if self.last_assessment_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

