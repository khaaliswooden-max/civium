"""
AI Ticket Classification and Routing.

NLP-based automatic ticket triage with multi-label classification
and intelligent routing to appropriate teams.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class KnowledgeBaseIndex(Protocol):
    """Protocol for knowledge base search."""

    def search(
        self,
        query: str,
        filter: dict[str, Any],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Search knowledge base for relevant articles."""
        ...


@dataclass
class TriageResult:
    """Result of ticket triage analysis."""

    ticket_id: str
    category: str
    subcategory: str
    priority: str
    sentiment: str
    assigned_team: str
    assigned_agent: str | None
    confidence: float
    suggested_solutions: list[dict[str, Any]]
    estimated_resolution_time: int  # minutes


class MockKnowledgeBase:
    """Mock knowledge base for development."""

    def search(
        self,
        query: str,
        filter: dict[str, Any],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Return mock KB articles."""
        return [
            {
                "id": "KB-001",
                "title": "Common Application Troubleshooting",
                "summary": "Steps to resolve common application errors and crashes.",
                "score": 0.85,
                "url": "/kb/articles/KB-001",
            },
            {
                "id": "KB-002",
                "title": "Password Reset Procedures",
                "summary": "How to reset passwords for various systems.",
                "score": 0.72,
                "url": "/kb/articles/KB-002",
            },
        ][:top_k]


class TicketTriageEngine:
    """
    AI-Powered Ticket Triage System.

    Capabilities:
    - Multi-label classification (category, subcategory)
    - Priority prediction based on content and context
    - Sentiment analysis for customer experience
    - Smart routing to appropriate teams/agents
    - Solution suggestion from knowledge base
    """

    CATEGORIES = [
        "hardware", "software", "network", "access", "email",
        "printing", "security", "facilities", "hr", "other",
    ]

    SUBCATEGORIES = {
        "hardware": ["laptop", "desktop", "monitor", "peripheral", "mobile"],
        "software": ["application_error", "installation", "update", "license", "compatibility"],
        "network": ["connectivity", "vpn", "wifi", "slow_speed", "outage"],
        "access": ["password_reset", "account_locked", "permissions", "new_account", "mfa"],
        "email": ["delivery", "calendar", "attachment", "spam", "configuration"],
        "security": ["malware", "phishing", "data_breach", "policy_violation", "incident"],
    }

    PRIORITIES = ["low", "medium", "high", "critical"]

    TEAM_ROUTING = {
        "hardware": "desktop_support",
        "software": "desktop_support",
        "network": "network_ops",
        "access": "identity_management",
        "email": "messaging_team",
        "security": "security_ops",
        "facilities": "facilities_mgmt",
        "hr": "hr_support",
        "printing": "desktop_support",
        "other": "service_desk",
    }

    def __init__(
        self,
        model_path: str | None = None,
        kb_index: KnowledgeBaseIndex | None = None,
    ) -> None:
        self.model_path = model_path
        self.kb_index = kb_index or MockKnowledgeBase()
        self._classifier: Any = None
        self._tokenizer: Any = None

    def triage_ticket(self, ticket: dict[str, Any]) -> TriageResult:
        """
        Perform full ticket triage.

        Args:
            ticket: Ticket data including subject, description, requester info.

        Returns:
            TriageResult with classification and routing decisions.
        """
        text = f"{ticket.get('subject', '')} {ticket.get('description', '')}"

        # 1. Classify category and subcategory
        category, subcategory, cat_confidence = self._classify_category(text)

        # 2. Predict priority
        priority, pri_confidence = self._predict_priority(text, ticket)

        # 3. Analyze sentiment
        sentiment = self._analyze_sentiment(text)

        # 4. Route to team/agent
        team, agent = self._route_ticket(category, priority, ticket)

        # 5. Suggest solutions
        solutions = self._suggest_solutions(text, category)

        # 6. Estimate resolution time
        est_time = self._estimate_resolution_time(category, priority)

        return TriageResult(
            ticket_id=ticket.get("id", "UNKNOWN"),
            category=category,
            subcategory=subcategory,
            priority=priority,
            sentiment=sentiment,
            assigned_team=team,
            assigned_agent=agent,
            confidence=min(cat_confidence, pri_confidence),
            suggested_solutions=solutions,
            estimated_resolution_time=est_time,
        )

    def _classify_category(self, text: str) -> tuple[str, str, float]:
        """Classify ticket category using keyword matching (mock implementation)."""
        text_lower = text.lower()

        # Simple keyword-based classification for development
        category_keywords = {
            "hardware": ["laptop", "computer", "monitor", "keyboard", "mouse", "printer"],
            "software": ["application", "app", "software", "install", "crash", "error", "update"],
            "network": ["network", "internet", "wifi", "vpn", "connection", "slow"],
            "access": ["password", "login", "access", "account", "locked", "permission"],
            "email": ["email", "outlook", "calendar", "meeting", "attachment"],
            "security": ["virus", "malware", "phishing", "security", "hack", "breach"],
        }

        best_category = "other"
        best_score = 0
        best_subcategory = "general"

        for category, keywords in category_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_category = category

        # Determine subcategory
        subcategories = self.SUBCATEGORIES.get(best_category, ["general"])
        for subcat in subcategories:
            if subcat.replace("_", " ") in text_lower or subcat in text_lower:
                best_subcategory = subcat
                break
        else:
            best_subcategory = subcategories[0] if subcategories else "general"

        confidence = min(0.95, 0.6 + (best_score * 0.1))
        return best_category, best_subcategory, confidence

    def _predict_priority(
        self,
        text: str,
        ticket: dict[str, Any],
    ) -> tuple[str, float]:
        """Predict ticket priority based on content and context."""
        priority_score = 0.0

        # Urgency keywords
        urgent_keywords = [
            "urgent", "asap", "critical", "down", "not working",
            "emergency", "blocked", "cannot access", "production",
            "outage", "immediately", "deadline",
        ]
        text_lower = text.lower()

        for keyword in urgent_keywords:
            if keyword in text_lower:
                priority_score += 0.2

        # VIP requester
        if ticket.get("requester_vip"):
            priority_score += 0.3

        # Business impact
        if ticket.get("users_affected", 1) > 10:
            priority_score += 0.3

        # System criticality
        critical_systems = ["production", "customer-facing", "revenue", "payroll"]
        if any(sys in text_lower for sys in critical_systems):
            priority_score += 0.2

        # Map to priority level
        if priority_score >= 0.7:
            priority = "critical"
        elif priority_score >= 0.5:
            priority = "high"
        elif priority_score >= 0.3:
            priority = "medium"
        else:
            priority = "low"

        return priority, min(1.0, priority_score + 0.3)

    def _analyze_sentiment(self, text: str) -> str:
        """Analyze customer sentiment using keyword matching."""
        text_lower = text.lower()

        negative_words = ["frustrated", "angry", "terrible", "awful", "unacceptable", "worst"]
        positive_words = ["thank", "appreciate", "great", "excellent", "helpful"]

        neg_count = sum(1 for w in negative_words if w in text_lower)
        pos_count = sum(1 for w in positive_words if w in text_lower)

        if neg_count > pos_count:
            return "negative"
        elif pos_count > neg_count:
            return "positive"
        return "neutral"

    def _route_ticket(
        self,
        category: str,
        priority: str,
        ticket: dict[str, Any],
    ) -> tuple[str, str | None]:
        """Intelligent ticket routing."""
        team = self.TEAM_ROUTING.get(category, "service_desk")

        # Agent selection for critical tickets
        agent = None
        if priority in ["critical", "high"]:
            agent = self._find_available_agent(team, skill=category)

        return team, agent

    def _find_available_agent(self, team: str, skill: str) -> str | None:
        """Find available agent with matching skills."""
        # Mock implementation - queries workforce management system in production
        return None

    def _suggest_solutions(
        self,
        text: str,
        category: str,
    ) -> list[dict[str, Any]]:
        """Search knowledge base for relevant solutions."""
        results = self.kb_index.search(
            query=text,
            filter={"category": category},
            top_k=3,
        )

        return [
            {
                "article_id": result["id"],
                "title": result["title"],
                "summary": result["summary"][:200],
                "confidence": result["score"],
                "url": result["url"],
            }
            for result in results
        ]

    def _estimate_resolution_time(self, category: str, priority: str) -> int:
        """Estimate resolution time in minutes."""
        base_times = {
            "hardware": 120,
            "software": 60,
            "network": 90,
            "access": 30,
            "email": 45,
            "security": 60,
            "facilities": 180,
            "printing": 45,
            "hr": 120,
            "other": 60,
        }

        priority_multipliers = {
            "critical": 0.5,
            "high": 0.75,
            "medium": 1.0,
            "low": 1.5,
        }

        base = base_times.get(category, 60)
        multiplier = priority_multipliers.get(priority, 1.0)

        return int(base * multiplier)

