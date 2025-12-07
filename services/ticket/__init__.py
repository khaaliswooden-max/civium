"""
Pro-Ticket: Service Management Module.

AI-powered ticket triage, classification, and SLA prediction
for intelligent service management.

Key Features:
- AI-Powered Triage with multi-label classification
- Predictive SLA Management
- Smart Routing to appropriate teams/agents
- Knowledge Base Integration for solution suggestions
"""

from services.ticket.ml.triage.classifier import (
    TicketTriageEngine,
    TriageResult,
)
from services.ticket.ml.sla.predictor import (
    SLAPrediction,
    SLAPredictionEngine,
)

__all__ = [
    "TicketTriageEngine",
    "TriageResult",
    "SLAPrediction",
    "SLAPredictionEngine",
]

