"""
Entity Assessment Database Models
=================================

SQLAlchemy ORM models for entity management and compliance assessment.

Tables:
- entities: Regulated organizations
- entity_assessments: Compliance assessments
- assessment_items: Individual requirement assessments
- entity_evidence: Compliance evidence
- entity_scores: Historical compliance scores

Version: 0.1.0
"""

from services.entity_assessment.models.entity import (
    EntityModel,
    EntityType,
    EntitySize,
)
from services.entity_assessment.models.assessment import (
    AssessmentModel,
    AssessmentItemModel,
    AssessmentStatus,
)
from services.entity_assessment.models.evidence import (
    EvidenceModel,
    EvidenceType,
    EvidenceStatus,
)
from services.entity_assessment.models.score import (
    ScoreHistoryModel,
    ScoreType,
)

__all__ = [
    # Entity
    "EntityModel",
    "EntityType",
    "EntitySize",
    # Assessment
    "AssessmentModel",
    "AssessmentItemModel",
    "AssessmentStatus",
    # Evidence
    "EvidenceModel",
    "EvidenceType",
    "EvidenceStatus",
    # Score
    "ScoreHistoryModel",
    "ScoreType",
]

