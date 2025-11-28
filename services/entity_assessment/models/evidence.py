"""
Evidence Database Model
=======================

SQLAlchemy ORM model for compliance evidence.

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
    Boolean,
    DateTime,
    Enum as SQLEnum,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from shared.database.postgres import Base


class EvidenceType(str, Enum):
    """Types of compliance evidence."""

    DOCUMENT = "document"  # Policy, procedure, report
    ATTESTATION = "attestation"  # Self-declaration
    CERTIFICATE = "certificate"  # Third-party certification
    AUDIT_REPORT = "audit_report"  # Audit findings
    SCREENSHOT = "screenshot"  # System evidence
    LOG = "log"  # System logs
    RECORD = "record"  # Business records
    CONTRACT = "contract"  # Agreements
    TRAINING = "training"  # Training records
    ZK_PROOF = "zk_proof"  # Zero-knowledge proof


class EvidenceStatus(str, Enum):
    """Evidence verification status."""

    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class EvidenceModel(Base):
    """
    SQLAlchemy model for compliance evidence.

    Evidence supports compliance claims and is linked to assessments
    and requirements.
    """

    __tablename__ = "evidence"
    __table_args__ = (
        Index("ix_evidence_entity", "entity_id"),
        Index("ix_evidence_type", "evidence_type"),
        Index("ix_evidence_status", "status"),
        Index("ix_evidence_created", "created_at"),
        Index("ix_evidence_expiry", "valid_until"),
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

    # Evidence info
    title = Column(String(255), nullable=False)
    description = Column(Text)
    evidence_type = Column(SQLEnum(EvidenceType), nullable=False, default=EvidenceType.DOCUMENT)
    status = Column(SQLEnum(EvidenceStatus), nullable=False, default=EvidenceStatus.PENDING)

    # Requirements this evidence supports
    requirement_ids = Column(ARRAY(String(100)), default=list)
    regulation_ids = Column(ARRAY(String(100)), default=list)

    # File information
    file_name = Column(String(255))
    file_path = Column(String(500))  # Storage path
    file_size = Column(Integer)  # Bytes
    file_type = Column(String(100))  # MIME type
    content_hash = Column(String(64))  # SHA-256

    # Cryptographic proofs
    zk_proof = Column(Text)  # Zero-knowledge proof data
    signature = Column(Text)  # Digital signature
    signer_did = Column(String(100))  # Signer's DID

    # Validity period
    valid_from = Column(DateTime(timezone=True), default=datetime.utcnow)
    valid_until = Column(DateTime(timezone=True))
    is_perpetual = Column(Boolean, default=False)  # No expiry

    # Verification
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime(timezone=True))
    verified_by = Column(UUID(as_uuid=True))
    verifier_name = Column(String(255))
    verification_method = Column(String(50))
    verification_notes = Column(Text)

    # Coverage
    coverage_percentage = Column(Integer, default=100)  # How much of requirement it covers

    # Source
    source = Column(String(255))  # Where evidence came from
    source_url = Column(String(500))  # External link
    external_id = Column(String(100))  # ID in external system

    # Metadata
    metadata = Column(JSON, default=dict)
    tags = Column(ARRAY(String(50)), default=list)

    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    deleted_at = Column(DateTime(timezone=True))  # Soft delete

    # Relationships
    entity = relationship("EntityModel", back_populates="evidence")

    def __repr__(self) -> str:
        return f"<Evidence {self.id}: {self.title} ({self.status.value})>"

    @property
    def is_valid(self) -> bool:
        """Check if evidence is currently valid."""
        if self.status != EvidenceStatus.VERIFIED:
            return False
        if self.is_perpetual:
            return True
        if self.valid_until and datetime.utcnow() > self.valid_until:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "entity_id": str(self.entity_id),
            "title": self.title,
            "description": self.description,
            "evidence_type": self.evidence_type.value,
            "status": self.status.value,
            "requirement_ids": self.requirement_ids or [],
            "file_name": self.file_name,
            "file_size": self.file_size,
            "content_hash": self.content_hash,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "verified": self.verified,
            "is_valid": self.is_valid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

