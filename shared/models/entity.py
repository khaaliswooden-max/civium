"""
Entity Models
=============

Models for entities (organizations, individuals) in the compliance system.

Version: 0.1.0
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EntityType(str, Enum):
    """Types of entities in the system."""

    INDIVIDUAL = "individual"
    CORPORATION = "corporation"
    PARTNERSHIP = "partnership"
    NON_PROFIT = "non_profit"
    GOVERNMENT = "government"
    SUPRANATIONAL = "supranational"


class ComplianceTier(str, Enum):
    """Compliance tier levels."""

    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"


class EntityBase(BaseModel):
    """Base entity fields."""

    name: str = Field(..., min_length=1, max_length=500)
    entity_type: EntityType
    sectors: list[str] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    size: str | None = Field(default=None, description="micro, small, medium, large")
    external_id: str | None = Field(
        default=None,
        description="External identifier (LEI, DUNS, etc.)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityCreate(EntityBase):
    """Request model for creating an entity."""

    @field_validator("jurisdictions")
    @classmethod
    def validate_jurisdictions(cls, v: list[str]) -> list[str]:
        """Ensure jurisdictions are uppercase ISO codes."""
        return [j.upper() for j in v]


class EntityUpdate(BaseModel):
    """Request model for updating an entity."""

    name: str | None = None
    entity_type: EntityType | None = None
    sectors: list[str] | None = None
    jurisdictions: list[str] | None = None
    size: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] | None = None


class Entity(EntityBase):
    """Full entity model with computed fields."""

    id: str = Field(..., description="Unique entity ID")

    # Compliance status
    compliance_tier: ComplianceTier = ComplianceTier.BASIC
    compliance_score: float | None = Field(
        default=None,
        ge=0,
        le=5,
        description="Compliance score (0-5)",
    )
    risk_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Risk score (0-1)",
    )

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_assessment_at: datetime | None = None

    # DID (if registered on blockchain)
    did: str | None = Field(default=None, description="Decentralized Identifier")

    class Config:
        from_attributes = True


class EntitySummary(BaseModel):
    """Lightweight entity summary for lists."""

    id: str
    name: str
    entity_type: EntityType
    compliance_tier: ComplianceTier
    compliance_score: float | None
    jurisdictions: list[str]

    class Config:
        from_attributes = True

