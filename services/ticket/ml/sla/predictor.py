"""
Predictive SLA Management.

ML-based breach prediction with proactive escalation triggers
for maintaining service level compliance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class SLAPrediction:
    """SLA breach prediction result."""

    ticket_id: str
    current_status: str
    sla_target: datetime
    time_remaining: timedelta
    breach_probability: float
    risk_level: str  # low, medium, high, critical
    contributing_factors: list[dict[str, Any]]
    recommended_actions: list[str]
    escalation_recommended: bool


class SLAPredictionEngine:
    """
    Predictive SLA Management Engine.

    Features:
    - Real-time breach probability calculation
    - Factor analysis for risk identification
    - Proactive escalation triggers
    - Workload optimization recommendations
    """

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path
        self._model: Any = None

    def predict_breach(
        self,
        ticket: dict[str, Any],
        agent_workload: dict[str, Any] | None = None,
    ) -> SLAPrediction:
        """
        Predict SLA breach probability.

        Args:
            ticket: Ticket data including status, SLA target, history.
            agent_workload: Current workload metrics for assigned agent.

        Returns:
            SLAPrediction with risk assessment and recommendations.
        """
        if agent_workload is None:
            agent_workload = {}

        features = self._extract_features(ticket, agent_workload)
        breach_prob = self._predict(features)

        # Determine risk level
        if breach_prob >= 0.8:
            risk_level = "critical"
        elif breach_prob >= 0.6:
            risk_level = "high"
        elif breach_prob >= 0.4:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Identify contributing factors
        factors = self._identify_factors(ticket, agent_workload)

        # Generate recommendations
        actions = self._recommend_actions(risk_level, factors)

        # Determine if escalation needed
        escalation = breach_prob >= 0.7 or risk_level in ["critical", "high"]

        # Parse SLA target
        sla_target = ticket.get("sla_target")
        if isinstance(sla_target, str):
            sla_target = datetime.fromisoformat(sla_target.replace("Z", "+00:00"))
        elif sla_target is None:
            # Default to 24 hours from now
            sla_target = datetime.utcnow() + timedelta(hours=24)

        now = datetime.utcnow()
        time_remaining = sla_target - now if sla_target > now else timedelta(0)

        return SLAPrediction(
            ticket_id=ticket.get("id", "UNKNOWN"),
            current_status=ticket.get("status", "open"),
            sla_target=sla_target,
            time_remaining=time_remaining,
            breach_probability=breach_prob,
            risk_level=risk_level,
            contributing_factors=factors,
            recommended_actions=actions,
            escalation_recommended=escalation,
        )

    def _extract_features(
        self,
        ticket: dict[str, Any],
        workload: dict[str, Any],
    ) -> list[float]:
        """Extract features for prediction model."""
        now = datetime.utcnow()
        sla_target = ticket.get("sla_target")

        if isinstance(sla_target, str):
            sla_target = datetime.fromisoformat(sla_target.replace("Z", "+00:00"))
        elif sla_target is None:
            sla_target = now + timedelta(hours=24)

        time_remaining = max(0, (sla_target - now).total_seconds() / 3600)

        return [
            time_remaining,
            ticket.get("complexity_score", 0.5),
            ticket.get("updates_count", 0),
            ticket.get("reassignment_count", 0),
            workload.get("agent_ticket_count", 0),
            workload.get("team_capacity_pct", 1.0),
            1 if ticket.get("priority") == "critical" else 0,
            1 if ticket.get("waiting_on_customer") else 0,
        ]

    def _predict(self, features: list[float]) -> float:
        """Run prediction model (mock implementation)."""
        # Simple rule-based prediction for development
        time_remaining = features[0]
        complexity = features[1]
        agent_load = features[4]
        is_critical = features[6]

        # Base probability from time remaining
        if time_remaining < 1:
            base_prob = 0.9
        elif time_remaining < 4:
            base_prob = 0.6
        elif time_remaining < 8:
            base_prob = 0.3
        else:
            base_prob = 0.1

        # Adjust for other factors
        prob = base_prob
        prob += complexity * 0.1
        prob += min(agent_load / 20, 0.2)
        if is_critical:
            prob += 0.1

        return min(0.99, max(0.01, prob))

    def _identify_factors(
        self,
        ticket: dict[str, Any],
        workload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Identify factors contributing to breach risk."""
        factors: list[dict[str, Any]] = []

        now = datetime.utcnow()
        sla_target = ticket.get("sla_target")

        if isinstance(sla_target, str):
            sla_target = datetime.fromisoformat(sla_target.replace("Z", "+00:00"))
        elif sla_target is None:
            sla_target = now + timedelta(hours=24)

        time_remaining = (sla_target - now).total_seconds() / 3600

        if time_remaining < 2:
            factors.append({
                "factor": "Time pressure",
                "impact": "high",
                "detail": f"Only {time_remaining:.1f} hours remaining",
            })

        if workload.get("agent_ticket_count", 0) > 10:
            factors.append({
                "factor": "Agent overloaded",
                "impact": "high",
                "detail": f"Agent has {workload['agent_ticket_count']} active tickets",
            })

        if ticket.get("reassignment_count", 0) > 2:
            factors.append({
                "factor": "Multiple reassignments",
                "impact": "medium",
                "detail": f"Reassigned {ticket['reassignment_count']} times",
            })

        if ticket.get("waiting_on_customer"):
            factors.append({
                "factor": "Awaiting customer response",
                "impact": "medium",
                "detail": "Customer response required to proceed",
            })

        if ticket.get("complexity_score", 0.5) > 0.7:
            factors.append({
                "factor": "High complexity",
                "impact": "medium",
                "detail": "Ticket marked as complex issue",
            })

        return factors

    def _recommend_actions(
        self,
        risk_level: str,
        factors: list[dict[str, Any]],
    ) -> list[str]:
        """Generate recommended actions."""
        actions: list[str] = []

        if risk_level in ["critical", "high"]:
            actions.append("Escalate to supervisor immediately")
            actions.append("Consider reassignment to senior agent")

        factor_types = [f["factor"] for f in factors]

        if "Agent overloaded" in factor_types:
            actions.append("Redistribute workload within team")

        if "Awaiting customer response" in factor_types:
            actions.append("Send follow-up to customer")
            actions.append("Attempt phone contact")

        if "Multiple reassignments" in factor_types:
            actions.append("Assign dedicated owner for completion")

        if "Time pressure" in factor_types:
            actions.append("Request overtime if needed")

        if "High complexity" in factor_types:
            actions.append("Consider pairing with specialist")

        return actions[:3]

