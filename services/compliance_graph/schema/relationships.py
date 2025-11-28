"""
Graph Relationship Definitions
==============================

Relationship types for the Compliance Graph.

Version: 0.1.0
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    """Neo4j relationship types."""

    # Requirement relationships
    BELONGS_TO = "BELONGS_TO"  # Requirement -> Regulation
    DEPENDS_ON = "DEPENDS_ON"  # Requirement -> Requirement
    CONFLICTS_WITH = "CONFLICTS_WITH"  # Requirement <-> Requirement
    SUPERSEDES = "SUPERSEDES"  # Requirement -> Requirement
    REFERENCES = "REFERENCES"  # Requirement -> Requirement

    # Scope relationships
    APPLIES_TO_JURISDICTION = "APPLIES_TO_JURISDICTION"  # Requirement -> Jurisdiction
    APPLIES_TO_SECTOR = "APPLIES_TO_SECTOR"  # Requirement -> Sector
    APPLIES_TO_ENTITY = "APPLIES_TO_ENTITY"  # Requirement -> Entity

    # Entity relationships
    HAS_STATE = "HAS_STATE"  # Entity -> ComplianceState
    OPERATES_IN = "OPERATES_IN"  # Entity -> Jurisdiction
    OPERATES_IN_SECTOR = "OPERATES_IN_SECTOR"  # Entity -> Sector

    # Compliance relationships
    SATISFIES = "SATISFIES"  # Evidence -> Requirement
    ATTESTS_TO = "ATTESTS_TO"  # Entity -> ComplianceState

    # Jurisdiction relationships
    PART_OF = "PART_OF"  # Jurisdiction -> Jurisdiction (child -> parent)

    # Sector relationships
    SUBSECTOR_OF = "SUBSECTOR_OF"  # Sector -> Sector


# =============================================================================
# Relationship Models
# =============================================================================


class BaseRelationship(BaseModel):
    """Base model for relationships."""

    created_at: datetime | None = None

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to Neo4j relationship properties."""
        props = {}
        if self.created_at:
            props["created_at"] = self.created_at.isoformat()
        return props


class BelongsTo(BaseRelationship):
    """
    Requirement BELONGS_TO Regulation.

    Links a requirement to its source regulation.
    """

    article_ref: str | None = None
    section_number: str | None = None

    def to_neo4j_properties(self) -> dict[str, Any]:
        props = super().to_neo4j_properties()
        if self.article_ref:
            props["article_ref"] = self.article_ref
        if self.section_number:
            props["section_number"] = self.section_number
        return props


class AppliesTo(BaseRelationship):
    """
    Requirement APPLIES_TO Entity/Jurisdiction/Sector.

    Defines the scope of a requirement.
    """

    # Applicability conditions
    condition: str | None = None  # Condition for applicability
    threshold: str | None = None  # Size/revenue threshold
    mandatory: bool = True

    def to_neo4j_properties(self) -> dict[str, Any]:
        props = super().to_neo4j_properties()
        props["mandatory"] = self.mandatory
        if self.condition:
            props["condition"] = self.condition
        if self.threshold:
            props["threshold"] = self.threshold
        return props


class HasState(BaseRelationship):
    """
    Entity HAS_STATE ComplianceState.

    Links an entity to its compliance status for a requirement.
    """

    current: bool = True  # Is this the current state?

    def to_neo4j_properties(self) -> dict[str, Any]:
        props = super().to_neo4j_properties()
        props["current"] = self.current
        return props


class Satisfies(BaseRelationship):
    """
    Evidence SATISFIES Requirement.

    Links evidence to the requirement it proves compliance for.
    """

    coverage: float = Field(default=1.0, ge=0.0, le=1.0, description="How much of the requirement is satisfied")
    verified: bool = False
    verification_method: str | None = None

    def to_neo4j_properties(self) -> dict[str, Any]:
        props = super().to_neo4j_properties()
        props["coverage"] = self.coverage
        props["verified"] = self.verified
        if self.verification_method:
            props["verification_method"] = self.verification_method
        return props


class DependsOn(BaseRelationship):
    """
    Requirement DEPENDS_ON Requirement.

    Indicates a requirement depends on another being satisfied first.
    """

    dependency_type: str = "prerequisite"  # prerequisite, corequisite, conditional
    mandatory: bool = True

    def to_neo4j_properties(self) -> dict[str, Any]:
        props = super().to_neo4j_properties()
        props["dependency_type"] = self.dependency_type
        props["mandatory"] = self.mandatory
        return props


class ConflictsWith(BaseRelationship):
    """
    Requirement CONFLICTS_WITH Requirement.

    Indicates two requirements that cannot both be satisfied.
    """

    conflict_type: str = "mutual_exclusion"  # mutual_exclusion, partial, conditional
    resolution: str | None = None  # How to resolve the conflict
    priority_override: str | None = None  # Which requirement takes precedence

    def to_neo4j_properties(self) -> dict[str, Any]:
        props = super().to_neo4j_properties()
        props["conflict_type"] = self.conflict_type
        if self.resolution:
            props["resolution"] = self.resolution
        if self.priority_override:
            props["priority_override"] = self.priority_override
        return props


class Supersedes(BaseRelationship):
    """
    Requirement SUPERSEDES Requirement.

    Indicates a requirement replaces an older one.
    """

    effective_date: datetime | None = None
    partial: bool = False  # Does it only partially supersede?

    def to_neo4j_properties(self) -> dict[str, Any]:
        props = super().to_neo4j_properties()
        props["partial"] = self.partial
        if self.effective_date:
            props["effective_date"] = self.effective_date.isoformat()
        return props


# =============================================================================
# Relationship Queries
# =============================================================================


def create_relationship_query(
    rel_type: RelationshipType,
    from_label: str,
    to_label: str,
    from_id_param: str = "from_id",
    to_id_param: str = "to_id",
    properties_param: str = "props",
) -> str:
    """
    Generate a Cypher query to create a relationship.

    Args:
        rel_type: Relationship type
        from_label: Source node label
        to_label: Target node label
        from_id_param: Parameter name for source ID
        to_id_param: Parameter name for target ID
        properties_param: Parameter name for relationship properties

    Returns:
        Cypher MERGE query string
    """
    return f"""
    MATCH (a:{from_label} {{id: ${from_id_param}}})
    MATCH (b:{to_label} {{id: ${to_id_param}}})
    MERGE (a)-[r:{rel_type.value}]->(b)
    SET r += ${properties_param}
    RETURN r
    """


def delete_relationship_query(
    rel_type: RelationshipType,
    from_label: str,
    to_label: str,
    from_id_param: str = "from_id",
    to_id_param: str = "to_id",
) -> str:
    """
    Generate a Cypher query to delete a relationship.

    Args:
        rel_type: Relationship type
        from_label: Source node label
        to_label: Target node label
        from_id_param: Parameter name for source ID
        to_id_param: Parameter name for target ID

    Returns:
        Cypher DELETE query string
    """
    return f"""
    MATCH (a:{from_label} {{id: ${from_id_param}}})-[r:{rel_type.value}]->(b:{to_label} {{id: ${to_id_param}}})
    DELETE r
    RETURN count(r) as deleted
    """

