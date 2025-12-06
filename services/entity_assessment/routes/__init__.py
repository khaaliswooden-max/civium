"""
Entity Assessment Routes
========================

API route handlers for the Entity Assessment Service.
"""

from services.entity_assessment.routes import assessments, entities, scores, tiers


__all__ = ["assessments", "entities", "scores", "tiers"]
