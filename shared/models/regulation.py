"""
Regulation Models
=================

Models for regulations and requirements.

Version: 0.1.0
"""

from datetime import UTC, datetime, date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RequirementTier(str, Enum):
    """Requirement complexity tiers."""

    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"


class VerificationMethod(str, Enum):
    """Methods for verifying compliance."""

    SELF_ATTESTATION = "self_attestation"
    DOCUMENT_REVIEW = "document_review"
    CRYPTOGRAPHIC_PROOF = "cryptographic_proof"
    ON_SITE_AUDIT = "on_site_audit"


class ChangeType(str, Enum):
    """Types of regulatory changes."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    SUPERSEDED = "superseded"


class Penalty(BaseModel):
    """Penalty information for a requirement."""

    monetary_max: float | None = None
    formula: str | None = Field(
        default=None,
        description="Formula for calculating penalty",
    )
    imprisonment_max_years: float | None = None


class Requirement(BaseModel):
    """A single compliance requirement."""

    id: str = Field(..., description="Unique requirement ID (e.g., REQ-GDPR-6-1-a)")
    regulation_id: str = Field(..., description="Parent regulation ID")
    article_ref: str | None = Field(default=None, description="Article/section reference")

    # Content
    natural_language: str = Field(..., description="Human-readable requirement text")
    formal_logic: str | None = Field(
        default=None,
        description="Formal logic representation",
    )
    summary: str | None = Field(default=None, description="Brief summary")

    # Classification
    tier: RequirementTier = RequirementTier.BASIC
    verification_method: VerificationMethod = VerificationMethod.SELF_ATTESTATION

    # Applicability
    sectors: list[str] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=list)

    # Penalties
    penalty: Penalty | None = None

    # Dates
    effective_date: date | None = None
    sunset_date: date | None = None

    # Metadata
    parsing_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Regulation(BaseModel):
    """A regulatory document/framework."""

    id: str = Field(..., description="Unique regulation ID (e.g., REG-GDPR)")
    name: str = Field(..., description="Full name of the regulation")
    short_name: str | None = Field(default=None, description="Common abbreviation")

    # Jurisdictions
    jurisdiction: str = Field(..., description="Primary jurisdiction code")
    jurisdictions: list[str] = Field(
        default_factory=list,
        description="All applicable jurisdictions",
    )

    # Classification
    sectors: list[str] = Field(default_factory=list)
    governance_layer: int = Field(
        default=5,
        ge=1,
        le=7,
        description="Governance layer (1-7)",
    )

    # Source
    source_url: str | None = None
    source_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of source document",
    )

    # Dates
    effective_date: date
    sunset_date: date | None = None

    # RML (Regulatory Markup Language) representation
    rml: dict[str, Any] = Field(
        default_factory=dict,
        description="Machine-readable representation",
    )

    # Parsing metadata
    parsing_metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RegulatoryChange(BaseModel):
    """A change to a regulation or requirement."""

    id: str = Field(default="", description="Change ID")
    regulation_id: str
    requirement_id: str | None = None
    change_type: ChangeType

    # Change details
    previous_version: dict[str, Any] | None = None
    new_version: dict[str, Any] | None = None
    diff: dict[str, Any] = Field(default_factory=dict)

    # Dates
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    effective_at: datetime | None = None

    # Notification
    notification_sent: bool = False


class RegulationSummary(BaseModel):
    """Lightweight regulation summary for lists."""

    id: str
    name: str
    short_name: str | None
    jurisdiction: str
    effective_date: date
    requirements_count: int = 0

