"""
Score History Database Model
============================

SQLAlchemy ORM model for tracking compliance score history.

Version: 0.1.0
"""

from datetime import datetime
from enum import Enum
from typing import Any
import uuid

from sqlalchemy import (
    Column,
    String,
    Text,
    Numeric,
    DateTime,
    Enum as SQLEnum,
    JSON,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from shared.database.postgres import Base


class ScoreType(str, Enum):
    """Types of compliance scores."""

    OVERALL = "overall"  # Overall compliance score
    JURISDICTION = "jurisdiction"  # Score for specific jurisdiction
    SECTOR = "sector"  # Score for specific sector
    REGULATION = "regulation"  # Score for specific regulation
    TIER = "tier"  # Score for specific tier
    RISK = "risk"  # Risk score


class ScoreHistoryModel(Base):
    """
    SQLAlchemy model for compliance score history.

    Tracks all compliance score changes over time for trend analysis
    and audit purposes.
    """

    __tablename__ = "score_history"
    __table_args__ = (
        Index("ix_score_history_entity", "entity_id"),
        Index("ix_score_history_type", "score_type"),
        Index("ix_score_history_recorded", "recorded_at"),
        Index("ix_score_history_entity_type", "entity_id", "score_type"),
        CheckConstraint("score >= 0 AND score <= 1", name="check_score_range"),
        {"schema": "core"},
    )

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Entity relationship
    entity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.entities.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Score info
    score_type = Column(SQLEnum(ScoreType), nullable=False, default=ScoreType.OVERALL)
    scope = Column(String(100))  # jurisdiction code, sector, regulation_id, etc.

    # The score
    score = Column(Numeric(5, 4), nullable=False)  # 0.0000 to 1.0000
    previous_score = Column(Numeric(5, 4))  # For tracking change

    # Change tracking
    change = Column(Numeric(6, 4))  # Difference from previous
    change_percentage = Column(Numeric(7, 4))  # Percentage change

    # Context
    assessment_id = Column(UUID(as_uuid=True))  # Assessment that triggered this score
    reason = Column(String(255))  # Why score changed

    # Breakdown (for overall scores)
    breakdown = Column(JSON, default=dict)  # Detailed score breakdown
    # Example: {"basic": 0.95, "standard": 0.85, "advanced": 0.70}

    # Statistics at this point
    total_requirements = Column(Numeric(10, 0))
    compliant_count = Column(Numeric(10, 0))
    non_compliant_count = Column(Numeric(10, 0))

    # Timestamp
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Metadata
    metadata = Column(JSON, default=dict)

    # Relationships
    entity = relationship("EntityModel", back_populates="score_history")

    def __repr__(self) -> str:
        return f"<ScoreHistory {self.id}: {self.entity_id} {self.score_type.value}={self.score}>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "entity_id": str(self.entity_id),
            "score_type": self.score_type.value,
            "scope": self.scope,
            "score": float(self.score),
            "previous_score": float(self.previous_score) if self.previous_score else None,
            "change": float(self.change) if self.change else None,
            "change_percentage": float(self.change_percentage) if self.change_percentage else None,
            "breakdown": self.breakdown,
            "total_requirements": int(self.total_requirements) if self.total_requirements else None,
            "compliant_count": int(self.compliant_count) if self.compliant_count else None,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }

