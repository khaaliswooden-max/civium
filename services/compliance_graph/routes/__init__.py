"""
Compliance Graph Routes
=======================

API route handlers for the Compliance Graph Service.
"""

from services.compliance_graph.routes import graph
from services.compliance_graph.routes import entities
from services.compliance_graph.routes import conflicts

__all__ = ["graph", "entities", "conflicts"]

