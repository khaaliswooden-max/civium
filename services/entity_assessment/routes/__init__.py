"""
Entity Assessment Routes
========================

API route handlers for the Entity Assessment Service.
"""

from services.entity_assessment.routes import entities
from services.entity_assessment.routes import assessments
from services.entity_assessment.routes import scores
from services.entity_assessment.routes import tiers

__all__ = ["entities", "assessments", "scores", "tiers"]

