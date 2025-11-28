"""
Graph Node Definitions
======================

Pydantic models for Neo4j node types in the Compliance Graph.

Version: 0.1.0
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ComplianceTier(str, Enum):
    """Compliance complexity tiers."""

    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"


class VerificationMethod(str, Enum):
    """Methods for verifying compliance."""

    SELF_ATTESTATION = "self_attestation"
    DOCUMENT_REVIEW = "document_review"
    CRYPTOGRAPHIC_PROOF = "cryptographic_proof"
    ON_SITE_AUDIT = "on_site_audit"
    AUTOMATED_MONITORING = "automated_monitoring"


class ComplianceStatus(str, Enum):
    """Entity compliance status."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    PENDING = "pending"
    EXEMPT = "exempt"
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    """Types of regulated entities."""

    CORPORATION = "corporation"
    SME = "sme"
    STARTUP = "startup"
    GOVERNMENT = "government"
    NON_PROFIT = "non_profit"
    INDIVIDUAL = "individual"
    PARTNERSHIP = "partnership"


class GovernanceLayer(int, Enum):
    """Seven-layer governance stack."""

    INDIVIDUAL = 1
    ORGANIZATIONAL = 2
    NATIONAL = 3
    REGIONAL = 4
    SECTORAL = 5
    UNIVERSAL = 6
    PLANETARY = 7


# =============================================================================
# Node Models
# =============================================================================


class RequirementNode(BaseModel):
    """
    Regulatory requirement node.

    Represents a single compliance requirement extracted from regulations.
    """

    # Core identity
    id: str = Field(..., description="Unique requirement ID (REQ-XX-XXXX)")
    regulation_id: str = Field(..., description="Parent regulation ID")
    article_ref: str = Field(..., description="Article/section reference")

    # Content
    natural_language: str = Field(..., description="Human-readable requirement text")
    formal_logic: str | None = Field(default=None, description="Formal logic representation")
    summary: str | None = Field(default=None, description="Brief summary")

    # Classification
    tier: ComplianceTier = Field(default=ComplianceTier.BASIC)
    verification_method: VerificationMethod = Field(default=VerificationMethod.SELF_ATTESTATION)
    governance_layer: GovernanceLayer = Field(default=GovernanceLayer.ORGANIZATIONAL)

    # Scope
    jurisdictions: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    applies_to_entity_types: list[str] = Field(default_factory=list)

    # Temporal
    effective_date: date | None = None
    sunset_date: date | None = None

    # Enforcement
    penalty_monetary_max: float | None = None
    penalty_formula: str | None = None

    # Metadata
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to Neo4j node properties."""
        props = {
            "id": self.id,
            "regulation_id": self.regulation_id,
            "article_ref": self.article_ref,
            "natural_language": self.natural_language,
            "tier": self.tier.value,
            "verification_method": self.verification_method.value,
            "governance_layer": self.governance_layer.value,
            "confidence": self.confidence,
        }

        if self.formal_logic:
            props["formal_logic"] = self.formal_logic
        if self.summary:
            props["summary"] = self.summary
        if self.effective_date:
            props["effective_date"] = self.effective_date.isoformat()
        if self.sunset_date:
            props["sunset_date"] = self.sunset_date.isoformat()
        if self.penalty_monetary_max is not None:
            props["penalty_monetary_max"] = self.penalty_monetary_max
        if self.penalty_formula:
            props["penalty_formula"] = self.penalty_formula
        if self.jurisdictions:
            props["jurisdictions"] = self.jurisdictions
        if self.sectors:
            props["sectors"] = self.sectors

        return props


class RegulationNode(BaseModel):
    """
    Regulation node.

    Represents a source regulation/law that contains requirements.
    """

    id: str = Field(..., description="Unique regulation ID (REG-XX-XXXX)")
    name: str = Field(..., description="Full regulation name")
    short_name: str | None = Field(default=None, description="Abbreviated name")

    # Classification
    jurisdiction: str = Field(..., description="Primary jurisdiction code")
    jurisdictions: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    governance_layer: GovernanceLayer = Field(default=GovernanceLayer.NATIONAL)

    # Source
    source_url: str | None = None
    source_hash: str | None = None

    # Temporal
    effective_date: date | None = None
    sunset_date: date | None = None
    last_amended: date | None = None

    # Statistics
    requirement_count: int = 0

    # Metadata
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to Neo4j node properties."""
        props = {
            "id": self.id,
            "name": self.name,
            "jurisdiction": self.jurisdiction,
            "governance_layer": self.governance_layer.value,
            "requirement_count": self.requirement_count,
        }

        if self.short_name:
            props["short_name"] = self.short_name
        if self.source_url:
            props["source_url"] = self.source_url
        if self.source_hash:
            props["source_hash"] = self.source_hash
        if self.effective_date:
            props["effective_date"] = self.effective_date.isoformat()
        if self.sunset_date:
            props["sunset_date"] = self.sunset_date.isoformat()
        if self.jurisdictions:
            props["jurisdictions"] = self.jurisdictions
        if self.sectors:
            props["sectors"] = self.sectors

        return props


class EntityNode(BaseModel):
    """
    Regulated entity node.

    Represents an organization or individual subject to regulations.
    """

    id: str = Field(..., description="Unique entity ID")
    name: str = Field(..., description="Entity name")
    entity_type: EntityType = Field(default=EntityType.CORPORATION)

    # Location
    jurisdiction: str = Field(..., description="Primary jurisdiction")
    jurisdictions: list[str] = Field(default_factory=list, description="All applicable jurisdictions")

    # Classification
    sectors: list[str] = Field(default_factory=list)
    size_category: str | None = None  # micro, small, medium, large
    employee_count: int | None = None
    annual_revenue: float | None = None

    # Identity
    registration_number: str | None = None
    did: str | None = None  # Decentralized identifier

    # Metadata
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to Neo4j node properties."""
        props = {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type.value,
            "jurisdiction": self.jurisdiction,
        }

        if self.jurisdictions:
            props["jurisdictions"] = self.jurisdictions
        if self.sectors:
            props["sectors"] = self.sectors
        if self.size_category:
            props["size_category"] = self.size_category
        if self.employee_count is not None:
            props["employee_count"] = self.employee_count
        if self.annual_revenue is not None:
            props["annual_revenue"] = self.annual_revenue
        if self.registration_number:
            props["registration_number"] = self.registration_number
        if self.did:
            props["did"] = self.did

        return props


class ComplianceStateNode(BaseModel):
    """
    Compliance state node.

    Represents an entity's compliance status for a specific requirement.
    """

    id: str = Field(..., description="Unique state ID")
    entity_id: str = Field(..., description="Entity this state belongs to")
    requirement_id: str = Field(..., description="Requirement being assessed")

    # Status
    status: ComplianceStatus = Field(default=ComplianceStatus.UNKNOWN)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Assessment
    assessed_at: datetime | None = None
    assessor: str | None = None  # User or system that made assessment
    assessment_method: VerificationMethod | None = None

    # Evidence
    evidence_ids: list[str] = Field(default_factory=list)

    # Validity
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    # Metadata
    notes: str | None = None

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to Neo4j node properties."""
        props = {
            "id": self.id,
            "entity_id": self.entity_id,
            "requirement_id": self.requirement_id,
            "status": self.status.value,
            "confidence": self.confidence,
        }

        if self.assessed_at:
            props["assessed_at"] = self.assessed_at.isoformat()
        if self.assessor:
            props["assessor"] = self.assessor
        if self.assessment_method:
            props["assessment_method"] = self.assessment_method.value
        if self.evidence_ids:
            props["evidence_ids"] = self.evidence_ids
        if self.valid_from:
            props["valid_from"] = self.valid_from.isoformat()
        if self.valid_until:
            props["valid_until"] = self.valid_until.isoformat()
        if self.notes:
            props["notes"] = self.notes

        return props


class JurisdictionNode(BaseModel):
    """
    Jurisdiction node.

    Represents a geographic/political jurisdiction.
    """

    id: str = Field(..., description="ISO jurisdiction code")
    name: str = Field(..., description="Full jurisdiction name")
    jurisdiction_type: str = Field(default="country")  # country, state, region, city

    # Hierarchy
    parent_id: str | None = None  # Parent jurisdiction
    governance_layer: GovernanceLayer = Field(default=GovernanceLayer.NATIONAL)

    # Metadata
    iso_code: str | None = None
    population: int | None = None

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to Neo4j node properties."""
        props = {
            "id": self.id,
            "name": self.name,
            "jurisdiction_type": self.jurisdiction_type,
            "governance_layer": self.governance_layer.value,
        }

        if self.parent_id:
            props["parent_id"] = self.parent_id
        if self.iso_code:
            props["iso_code"] = self.iso_code
        if self.population is not None:
            props["population"] = self.population

        return props


class SectorNode(BaseModel):
    """
    Industry sector node.

    Represents an industry or business sector.
    """

    id: str = Field(..., description="Sector code")
    name: str = Field(..., description="Sector name")

    # Classification
    parent_id: str | None = None  # Parent sector for hierarchies
    naics_code: str | None = None  # North American Industry Classification
    isic_code: str | None = None  # International Standard Industrial Classification

    # Regulation metrics
    regulation_count: int = 0
    requirement_count: int = 0

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to Neo4j node properties."""
        props = {
            "id": self.id,
            "name": self.name,
            "regulation_count": self.regulation_count,
            "requirement_count": self.requirement_count,
        }

        if self.parent_id:
            props["parent_id"] = self.parent_id
        if self.naics_code:
            props["naics_code"] = self.naics_code
        if self.isic_code:
            props["isic_code"] = self.isic_code

        return props


class EvidenceNode(BaseModel):
    """
    Compliance evidence node.

    Represents evidence that supports compliance claims.
    """

    id: str = Field(..., description="Unique evidence ID")
    entity_id: str = Field(..., description="Entity that owns this evidence")

    # Evidence type
    evidence_type: str = Field(default="document")  # document, attestation, audit, proof

    # Content
    title: str = Field(..., description="Evidence title")
    description: str | None = None
    content_hash: str | None = None  # Hash of evidence content

    # Cryptographic proof (if applicable)
    zk_proof: str | None = None  # Zero-knowledge proof
    signature: str | None = None

    # Temporal
    created_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    # Verification
    verified: bool = False
    verified_by: str | None = None
    verified_at: datetime | None = None

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to Neo4j node properties."""
        props = {
            "id": self.id,
            "entity_id": self.entity_id,
            "evidence_type": self.evidence_type,
            "title": self.title,
            "verified": self.verified,
        }

        if self.description:
            props["description"] = self.description
        if self.content_hash:
            props["content_hash"] = self.content_hash
        if self.zk_proof:
            props["zk_proof"] = self.zk_proof
        if self.signature:
            props["signature"] = self.signature
        if self.valid_from:
            props["valid_from"] = self.valid_from.isoformat()
        if self.valid_until:
            props["valid_until"] = self.valid_until.isoformat()
        if self.verified_by:
            props["verified_by"] = self.verified_by
        if self.verified_at:
            props["verified_at"] = self.verified_at.isoformat()

        return props

