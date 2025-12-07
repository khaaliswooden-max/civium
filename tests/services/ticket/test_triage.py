"""Tests for ticket triage engine."""

import pytest

from services.ticket.ml.triage.classifier import (
    TicketTriageEngine,
    TriageResult,
)


@pytest.fixture
def engine() -> TicketTriageEngine:
    """Create triage engine for testing."""
    return TicketTriageEngine()


class TestTicketTriageEngine:
    """Tests for TicketTriageEngine."""

    def test_triage_software_ticket(self, engine: TicketTriageEngine) -> None:
        """Test triage of a software-related ticket."""
        ticket = {
            "id": "TKT-001",
            "subject": "Application crash when opening file",
            "description": "The software crashes every time I try to open a PDF file.",
        }

        result = engine.triage_ticket(ticket)

        assert isinstance(result, TriageResult)
        assert result.ticket_id == "TKT-001"
        assert result.category == "software"
        assert result.assigned_team == "desktop_support"
        assert result.priority in ["low", "medium", "high", "critical"]
        assert result.confidence > 0

    def test_triage_network_ticket(self, engine: TicketTriageEngine) -> None:
        """Test triage of a network-related ticket."""
        ticket = {
            "id": "TKT-002",
            "subject": "Cannot connect to VPN",
            "description": "Internet connection is slow and VPN keeps disconnecting.",
        }

        result = engine.triage_ticket(ticket)

        assert result.category == "network"
        assert result.assigned_team == "network_ops"

    def test_triage_urgent_ticket(self, engine: TicketTriageEngine) -> None:
        """Test triage correctly identifies urgent tickets."""
        ticket = {
            "id": "TKT-003",
            "subject": "URGENT: Production system down",
            "description": "Critical production server is not responding. Need help ASAP!",
            "requester_vip": True,
            "users_affected": 50,
        }

        result = engine.triage_ticket(ticket)

        assert result.priority in ["high", "critical"]

    def test_triage_access_ticket(self, engine: TicketTriageEngine) -> None:
        """Test triage of access-related ticket."""
        ticket = {
            "id": "TKT-004",
            "subject": "Password reset needed",
            "description": "I forgot my password and cannot log in to my account.",
        }

        result = engine.triage_ticket(ticket)

        assert result.category == "access"
        assert result.assigned_team == "identity_management"

    def test_suggest_solutions(self, engine: TicketTriageEngine) -> None:
        """Test solution suggestions from knowledge base."""
        text = "Application is crashing"
        category = "software"

        solutions = engine._suggest_solutions(text, category)

        assert isinstance(solutions, list)
        assert len(solutions) > 0
        assert "article_id" in solutions[0]
        assert "title" in solutions[0]

    def test_estimate_resolution_time(self, engine: TicketTriageEngine) -> None:
        """Test resolution time estimation."""
        # Access tickets should be faster
        access_time = engine._estimate_resolution_time("access", "medium")
        # Hardware tickets should take longer
        hardware_time = engine._estimate_resolution_time("hardware", "medium")

        assert access_time < hardware_time

        # Critical priority should be faster
        critical_time = engine._estimate_resolution_time("software", "critical")
        low_time = engine._estimate_resolution_time("software", "low")

        assert critical_time < low_time

    def test_sentiment_analysis(self, engine: TicketTriageEngine) -> None:
        """Test sentiment analysis."""
        negative = "I am so frustrated! This is terrible service!"
        positive = "Thank you for the great help!"
        neutral = "I need help with my computer."

        assert engine._analyze_sentiment(negative) == "negative"
        assert engine._analyze_sentiment(positive) == "positive"
        assert engine._analyze_sentiment(neutral) == "neutral"

