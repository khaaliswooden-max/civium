"""
Regulatory Intelligence Routes
==============================

API route handlers for the Regulatory Intelligence Service.
"""

from services.regulatory_intelligence.routes import regulations
from services.regulatory_intelligence.routes import requirements
from services.regulatory_intelligence.routes import ingestion

__all__ = ["regulations", "requirements", "ingestion"]

