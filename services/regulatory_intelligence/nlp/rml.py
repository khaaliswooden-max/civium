"""
RML Generator Module
====================

Generates Regulatory Markup Language (RML) from parsed requirements.

RML is a machine-readable format for representing regulatory requirements,
designed for:
- Interoperability between compliance systems
- Automated compliance checking
- Version tracking and diffing
- Cross-jurisdictional mapping

Version: 0.1.0
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from shared.logging import get_logger
from services.regulatory_intelligence.nlp.parser import (
    ParsedRegulation,
    ParsedRequirement,
    ComplianceTier,
    RequirementType,
    VerificationMethod,
)

logger = get_logger(__name__)


class RMLVersion(str, Enum):
    """RML schema versions."""

    V1_0 = "1.0"
    V1_1 = "1.1"


@dataclass
class RMLRequirement:
    """RML representation of a single requirement."""

    # Core identification
    id: str
    regulation_id: str
    article_ref: str

    # Content
    text: str
    summary: str | None = None
    formal_logic: str | None = None

    # Classification
    type: str = "obligation"
    tier: str = "basic"
    verification_method: str = "self_attestation"

    # Applicability scope
    scope: dict[str, Any] = field(default_factory=lambda: {
        "entities": [],
        "sectors": [],
        "jurisdictions": [],
        "size_thresholds": {},
    })

    # Temporal validity
    temporal: dict[str, Any] = field(default_factory=lambda: {
        "effective_date": None,
        "sunset_date": None,
        "review_period_days": None,
    })

    # Enforcement
    enforcement: dict[str, Any] = field(default_factory=lambda: {
        "penalty_monetary_max": None,
        "penalty_formula": None,
        "penalty_imprisonment_max": None,
        "enforcement_authority": None,
    })

    # Cross-references
    references: list[dict[str, str]] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "regulation_id": self.regulation_id,
            "article_ref": self.article_ref,
            "text": self.text,
            "summary": self.summary,
            "formal_logic": self.formal_logic,
            "type": self.type,
            "tier": self.tier,
            "verification_method": self.verification_method,
            "scope": self.scope,
            "temporal": self.temporal,
            "enforcement": self.enforcement,
            "references": self.references,
            "metadata": self.metadata,
        }


@dataclass
class RMLDocument:
    """Complete RML document for a regulation."""

    # Schema version
    schema_version: str = RMLVersion.V1_0.value

    # Regulation identification
    id: str = ""
    name: str = ""
    short_name: str | None = None

    # Jurisdiction and scope
    jurisdiction: str = ""
    jurisdictions: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)
    governance_layer: int = 5  # 1-7 in the seven-layer stack

    # Source information
    source: dict[str, Any] = field(default_factory=lambda: {
        "url": None,
        "hash": None,
        "retrieved_at": None,
    })

    # Temporal information
    effective_date: str | None = None
    sunset_date: str | None = None

    # Requirements
    requirements: list[RMLRequirement] = field(default_factory=list)

    # Statistics
    statistics: dict[str, Any] = field(default_factory=lambda: {
        "total_requirements": 0,
        "by_tier": {"basic": 0, "standard": 0, "advanced": 0},
        "by_type": {},
    })

    # Document hash for change detection
    document_hash: str = ""

    # Generation metadata
    generated_at: str = ""
    generator_version: str = "0.1.0"
    parsing_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": f"https://civium.io/schemas/rml/v{self.schema_version}",
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "jurisdiction": self.jurisdiction,
            "jurisdictions": self.jurisdictions,
            "sectors": self.sectors,
            "governance_layer": self.governance_layer,
            "source": self.source,
            "effective_date": self.effective_date,
            "sunset_date": self.sunset_date,
            "requirements": [r.to_dict() for r in self.requirements],
            "statistics": self.statistics,
            "document_hash": self.document_hash,
            "generated_at": self.generated_at,
            "generator_version": self.generator_version,
            "parsing_notes": self.parsing_notes,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RMLDocument":
        """Create RMLDocument from dictionary."""
        requirements = [
            RMLRequirement(**req_data)
            for req_data in data.get("requirements", [])
        ]

        return cls(
            schema_version=data.get("schema_version", RMLVersion.V1_0.value),
            id=data.get("id", ""),
            name=data.get("name", ""),
            short_name=data.get("short_name"),
            jurisdiction=data.get("jurisdiction", ""),
            jurisdictions=data.get("jurisdictions", []),
            sectors=data.get("sectors", []),
            governance_layer=data.get("governance_layer", 5),
            source=data.get("source", {}),
            effective_date=data.get("effective_date"),
            sunset_date=data.get("sunset_date"),
            requirements=requirements,
            statistics=data.get("statistics", {}),
            document_hash=data.get("document_hash", ""),
            generated_at=data.get("generated_at", ""),
            generator_version=data.get("generator_version", ""),
            parsing_notes=data.get("parsing_notes", []),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "RMLDocument":
        """Create RMLDocument from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


class RMLGenerator:
    """
    Generates RML documents from parsed regulations.

    Handles:
    - Converting ParsedRegulation to RML format
    - Computing document hashes
    - Generating statistics
    - Version management
    """

    def __init__(
        self,
        schema_version: RMLVersion = RMLVersion.V1_0,
        include_formal_logic: bool = True,
    ) -> None:
        """
        Initialize the RML generator.

        Args:
            schema_version: RML schema version to generate
            include_formal_logic: Include formal logic in output
        """
        self.schema_version = schema_version
        self.include_formal_logic = include_formal_logic

    def generate(
        self,
        regulation: ParsedRegulation,
        source_url: str | None = None,
        source_hash: str | None = None,
    ) -> RMLDocument:
        """
        Generate RML document from parsed regulation.

        Args:
            regulation: Parsed regulation to convert
            source_url: Original source URL
            source_hash: Hash of source document

        Returns:
            RMLDocument ready for storage/transmission
        """
        # Convert requirements
        rml_requirements = [
            self._convert_requirement(req)
            for req in regulation.requirements
        ]

        # Compute statistics
        statistics = self._compute_statistics(rml_requirements)

        # Create document
        doc = RMLDocument(
            schema_version=self.schema_version.value,
            id=regulation.id,
            name=regulation.name,
            short_name=regulation.short_name,
            jurisdiction=regulation.jurisdiction,
            jurisdictions=regulation.jurisdictions,
            sectors=regulation.sectors,
            source={
                "url": source_url,
                "hash": source_hash,
                "retrieved_at": datetime.now(UTC).isoformat(),
            },
            effective_date=(
                regulation.effective_date.isoformat()
                if regulation.effective_date
                else None
            ),
            sunset_date=(
                regulation.sunset_date.isoformat()
                if regulation.sunset_date
                else None
            ),
            requirements=rml_requirements,
            statistics=statistics,
            generated_at=datetime.now(UTC).isoformat(),
            generator_version="0.1.0",
            parsing_notes=regulation.parsing_notes,
        )

        # Compute document hash
        doc.document_hash = self._compute_hash(doc)

        logger.info(
            "rml_generated",
            regulation_id=regulation.id,
            requirements=len(rml_requirements),
            hash=doc.document_hash[:16],
        )

        return doc

    def _convert_requirement(self, req: ParsedRequirement) -> RMLRequirement:
        """Convert ParsedRequirement to RMLRequirement."""
        return RMLRequirement(
            id=req.id,
            regulation_id=req.regulation_id,
            article_ref=req.article_ref,
            text=req.natural_language,
            summary=req.summary,
            formal_logic=req.formal_logic if self.include_formal_logic else None,
            type=req.requirement_type.value,
            tier=req.tier.value,
            verification_method=req.verification_method.value,
            scope={
                "entities": req.applies_to,
                "sectors": req.sectors,
                "jurisdictions": req.jurisdictions,
                "size_thresholds": {},
            },
            temporal={
                "effective_date": (
                    req.effective_date.isoformat()
                    if req.effective_date
                    else None
                ),
                "sunset_date": (
                    req.sunset_date.isoformat()
                    if req.sunset_date
                    else None
                ),
                "review_period_days": None,
            },
            enforcement={
                "penalty_monetary_max": req.penalty_monetary_max,
                "penalty_formula": req.penalty_formula,
                "penalty_imprisonment_max": req.penalty_imprisonment_max,
                "enforcement_authority": None,
            },
            references=[
                {"type": "depends_on", "target": ref}
                for ref in req.depends_on
            ] + [
                {"type": "conflicts_with", "target": ref}
                for ref in req.conflicts_with
            ] + [
                {"type": "cites", "target": ref}
                for ref in req.references
            ],
            metadata={
                "confidence": req.confidence,
                "parsing_notes": req.parsing_notes,
            },
        )

    def _compute_statistics(
        self,
        requirements: list[RMLRequirement],
    ) -> dict[str, Any]:
        """Compute statistics for the regulation."""
        by_tier = {"basic": 0, "standard": 0, "advanced": 0}
        by_type: dict[str, int] = {}
        by_verification: dict[str, int] = {}

        for req in requirements:
            # Count by tier
            tier = req.tier
            if tier in by_tier:
                by_tier[tier] += 1

            # Count by type
            req_type = req.type
            by_type[req_type] = by_type.get(req_type, 0) + 1

            # Count by verification method
            method = req.verification_method
            by_verification[method] = by_verification.get(method, 0) + 1

        return {
            "total_requirements": len(requirements),
            "by_tier": by_tier,
            "by_type": by_type,
            "by_verification_method": by_verification,
        }

    def _compute_hash(self, doc: RMLDocument) -> str:
        """
        Compute content hash for change detection.

        Uses a deterministic subset of fields to allow
        comparing regulations across versions.
        """
        # Create hashable content (excluding metadata that changes)
        content = {
            "id": doc.id,
            "name": doc.name,
            "requirements": [
                {
                    "article_ref": r.article_ref,
                    "text": r.text,
                    "type": r.type,
                }
                for r in doc.requirements
            ],
        }

        # Compute SHA-256
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def diff(
        self,
        old_doc: RMLDocument,
        new_doc: RMLDocument,
    ) -> dict[str, Any]:
        """
        Compute differences between two RML documents.

        Returns:
            Dictionary describing the changes
        """
        changes: dict[str, Any] = {
            "has_changes": old_doc.document_hash != new_doc.document_hash,
            "old_hash": old_doc.document_hash,
            "new_hash": new_doc.document_hash,
            "added_requirements": [],
            "removed_requirements": [],
            "modified_requirements": [],
            "metadata_changes": {},
        }

        # Index requirements by ID
        old_reqs = {r.id: r for r in old_doc.requirements}
        new_reqs = {r.id: r for r in new_doc.requirements}

        old_ids = set(old_reqs.keys())
        new_ids = set(new_reqs.keys())

        # Find added requirements
        for req_id in new_ids - old_ids:
            changes["added_requirements"].append({
                "id": req_id,
                "article_ref": new_reqs[req_id].article_ref,
                "text": new_reqs[req_id].text[:200],
            })

        # Find removed requirements
        for req_id in old_ids - new_ids:
            changes["removed_requirements"].append({
                "id": req_id,
                "article_ref": old_reqs[req_id].article_ref,
                "text": old_reqs[req_id].text[:200],
            })

        # Find modified requirements
        for req_id in old_ids & new_ids:
            old_req = old_reqs[req_id]
            new_req = new_reqs[req_id]

            if old_req.text != new_req.text:
                changes["modified_requirements"].append({
                    "id": req_id,
                    "article_ref": new_req.article_ref,
                    "changes": {
                        "text": {
                            "old": old_req.text[:200],
                            "new": new_req.text[:200],
                        }
                    },
                })

        # Check metadata changes
        if old_doc.name != new_doc.name:
            changes["metadata_changes"]["name"] = {
                "old": old_doc.name,
                "new": new_doc.name,
            }

        if old_doc.effective_date != new_doc.effective_date:
            changes["metadata_changes"]["effective_date"] = {
                "old": old_doc.effective_date,
                "new": new_doc.effective_date,
            }

        return changes

    def validate(self, doc: RMLDocument) -> list[str]:
        """
        Validate an RML document.

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []

        # Required fields
        if not doc.id:
            errors.append("Missing required field: id")
        if not doc.name:
            errors.append("Missing required field: name")
        if not doc.jurisdiction:
            errors.append("Missing required field: jurisdiction")

        # Requirements validation
        for i, req in enumerate(doc.requirements):
            if not req.id:
                errors.append(f"Requirement {i}: Missing id")
            if not req.text:
                errors.append(f"Requirement {i}: Missing text")
            if not req.article_ref:
                errors.append(f"Requirement {i}: Missing article_ref")

            # Tier validation
            if req.tier not in ["basic", "standard", "advanced"]:
                errors.append(f"Requirement {req.id}: Invalid tier '{req.tier}'")

        # Date validation
        if doc.effective_date:
            try:
                date.fromisoformat(doc.effective_date)
            except ValueError:
                errors.append(f"Invalid effective_date format: {doc.effective_date}")

        return errors

