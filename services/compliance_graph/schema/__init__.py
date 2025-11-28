"""
Compliance Graph Schema
=======================

Neo4j schema definitions for the Civium Compliance Graph.

Node Types:
- Requirement: Regulatory requirements
- Regulation: Source regulations
- Entity: Regulated entities  
- ComplianceState: Entity compliance status
- Jurisdiction: Geographic jurisdictions
- Sector: Industry sectors
- Evidence: Compliance evidence

Relationships:
- BELONGS_TO: Requirement -> Regulation
- APPLIES_TO: Requirement -> Entity/Sector/Jurisdiction
- HAS_STATE: Entity -> ComplianceState
- SATISFIES: Evidence -> Requirement
- DEPENDS_ON: Requirement -> Requirement
- CONFLICTS_WITH: Requirement -> Requirement
- SUPERSEDES: Requirement -> Requirement

Version: 0.1.0
"""

from services.compliance_graph.schema.nodes import (
    RequirementNode,
    RegulationNode,
    EntityNode,
    ComplianceStateNode,
    JurisdictionNode,
    SectorNode,
    EvidenceNode,
)
from services.compliance_graph.schema.relationships import (
    RelationshipType,
    BelongsTo,
    AppliesTo,
    HasState,
    Satisfies,
    DependsOn,
    ConflictsWith,
    Supersedes,
)
from services.compliance_graph.schema.constraints import (
    SCHEMA_CONSTRAINTS,
    SCHEMA_INDEXES,
    apply_schema,
)

__all__ = [
    # Nodes
    "RequirementNode",
    "RegulationNode",
    "EntityNode",
    "ComplianceStateNode",
    "JurisdictionNode",
    "SectorNode",
    "EvidenceNode",
    # Relationships
    "RelationshipType",
    "BelongsTo",
    "AppliesTo",
    "HasState",
    "Satisfies",
    "DependsOn",
    "ConflictsWith",
    "Supersedes",
    # Schema management
    "SCHEMA_CONSTRAINTS",
    "SCHEMA_INDEXES",
    "apply_schema",
]

