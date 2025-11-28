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

from services.compliance_graph.routes import graph
from services.compliance_graph.routes import entities
from services.compliance_graph.routes import conflicts
from services.compliance_graph.routes import compliance
from services.compliance_graph.routes import paths
from services.compliance_graph.routes import ingestion

__all__ = ["graph", "entities", "conflicts", "compliance", "paths", "ingestion"]

