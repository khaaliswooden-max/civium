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

from services.regulatory_intelligence.routes import ingestion, pipeline, regulations, requirements


__all__ = ["ingestion", "pipeline", "regulations", "requirements"]
