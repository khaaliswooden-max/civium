"""
Compliance Graph Routes
=======================

API route handlers for the Compliance Graph Service.

Routes:
- graph: Graph database operations
- entities: Entity management
- conflicts: Conflict detection
- compliance: Compliance status and gap analysis
- paths: Path discovery and dependency analysis
- ingestion: Graph data ingestion
"""

from services.compliance_graph.routes import (
    compliance,
    conflicts,
    entities,
    graph,
    ingestion,
    paths,
)


__all__ = ["compliance", "conflicts", "entities", "graph", "ingestion", "paths"]
