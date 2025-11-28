"""
Regulatory Intelligence Routes
==============================

API route handlers for the Regulatory Intelligence Service.

Routes:
- regulations: CRUD operations for regulations
- requirements: Requirement management
- ingestion: Document ingestion
- pipeline: Complete NLP processing pipeline
"""

from services.regulatory_intelligence.routes import regulations
from services.regulatory_intelligence.routes import requirements
from services.regulatory_intelligence.routes import ingestion
from services.regulatory_intelligence.routes import pipeline

__all__ = ["regulations", "requirements", "ingestion", "pipeline"]

