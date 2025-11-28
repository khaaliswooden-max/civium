"""
Shared Models
=============

Pydantic models shared across Civium services.

Models:
- Entity models (Entity, EntityCreate, EntityUpdate)
- Regulation models (Regulation, Requirement)
- Assessment models (Assessment, CriterionScore)
- Compliance models (ComplianceState, ComplianceEvent)
"""

from shared.models.entity import (
    Entity,
    EntityCreate,
    EntityUpdate,
    EntityType,
    ComplianceTier,
    EntitySummary,
)
from shared.models.regulation import (
    Regulation,
    Requirement,
    RequirementTier,
    VerificationMethod,
    RegulatoryChange,
)
from shared.models.assessment import (
    Assessment,
    AssessmentCreate,
    AssessmentStatus,
    CriterionScore,
)
from shared.models.compliance import (
    ComplianceState,
    ComplianceEvent,
    ComplianceGap,
    ComplianceScore,
)
from shared.models.common import (
    BaseResponse,
    PaginatedResponse,
    ErrorResponse,
    HealthResponse,
)

__all__ = [
    # Entity
    "Entity",
    "EntityCreate",
    "EntityUpdate",
    "EntityType",
    "ComplianceTier",
    "EntitySummary",
    # Regulation
    "Regulation",
    "Requirement",
    "RequirementTier",
    "VerificationMethod",
    "RegulatoryChange",
    # Assessment
    "Assessment",
    "AssessmentCreate",
    "AssessmentStatus",
    "CriterionScore",
    # Compliance
    "ComplianceState",
    "ComplianceEvent",
    "ComplianceGap",
    "ComplianceScore",
    # Common
    "BaseResponse",
    "PaginatedResponse",
    "ErrorResponse",
    "HealthResponse",
]

