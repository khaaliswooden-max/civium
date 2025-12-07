"""Tests for SLA prediction engine."""

import pytest
from datetime import datetime, timedelta

from services.ticket.ml.sla.predictor import (
    SLAPredictionEngine,
    SLAPrediction,
)


@pytest.fixture
def engine() -> SLAPredictionEngine:
    """Create SLA prediction engine for testing."""
    return SLAPredictionEngine()


class TestSLAPredictionEngine:
    """Tests for SLAPredictionEngine."""

    def test_predict_low_risk(self, engine: SLAPredictionEngine) -> None:
        """Test prediction for low-risk ticket."""
        ticket = {
            "id": "TKT-001",
            "status": "open",
            "priority": "low",
            "sla_target": (datetime.utcnow() + timedelta(hours=48)).isoformat(),
        }

        result = engine.predict_breach(ticket)

        assert isinstance(result, SLAPrediction)
        assert result.ticket_id == "TKT-001"
        assert result.risk_level == "low"
        assert result.breach_probability < 0.4
        assert not result.escalation_recommended

    def test_predict_high_risk_time_pressure(self, engine: SLAPredictionEngine) -> None:
        """Test prediction for ticket with time pressure."""
        ticket = {
            "id": "TKT-002",
            "status": "open",
            "priority": "high",
            "sla_target": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }

        workload = {"agent_ticket_count": 15}

        result = engine.predict_breach(ticket, workload)

        assert result.risk_level in ["high", "critical"]
        assert result.breach_probability > 0.5
        assert result.escalation_recommended
        assert any(f["factor"] == "Time pressure" for f in result.contributing_factors)

    def test_predict_with_agent_overload(self, engine: SLAPredictionEngine) -> None:
        """Test prediction considers agent workload."""
        ticket = {
            "id": "TKT-003",
            "status": "in_progress",
            "priority": "medium",
            "sla_target": (datetime.utcnow() + timedelta(hours=12)).isoformat(),
        }

        workload = {"agent_ticket_count": 20, "team_capacity_pct": 0.9}

        result = engine.predict_breach(ticket, workload)

        assert any(f["factor"] == "Agent overloaded" for f in result.contributing_factors)

    def test_predict_with_reassignments(self, engine: SLAPredictionEngine) -> None:
        """Test prediction flags multiple reassignments."""
        ticket = {
            "id": "TKT-004",
            "status": "open",
            "priority": "medium",
            "sla_target": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
            "reassignment_count": 5,
        }

        result = engine.predict_breach(ticket)

        assert any(f["factor"] == "Multiple reassignments" for f in result.contributing_factors)

    def test_predict_customer_waiting(self, engine: SLAPredictionEngine) -> None:
        """Test prediction handles waiting on customer."""
        ticket = {
            "id": "TKT-005",
            "status": "pending",
            "priority": "medium",
            "sla_target": (datetime.utcnow() + timedelta(hours=4)).isoformat(),
            "waiting_on_customer": True,
        }

        result = engine.predict_breach(ticket)

        assert any(f["factor"] == "Awaiting customer response" for f in result.contributing_factors)

    def test_recommended_actions(self, engine: SLAPredictionEngine) -> None:
        """Test that recommended actions are provided."""
        ticket = {
            "id": "TKT-006",
            "status": "open",
            "priority": "critical",
            "sla_target": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }

        result = engine.predict_breach(ticket)

        assert len(result.recommended_actions) > 0
        assert len(result.recommended_actions) <= 3

