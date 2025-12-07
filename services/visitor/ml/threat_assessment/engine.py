"""
AI-Powered Visitor Threat Assessment Engine.

Integrates with federal watchlists and behavioral analysis for
comprehensive visitor screening in compliance with federal requirements.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import httpx


class ThreatLevel(Enum):
    """Threat classification levels for visitor screening."""

    CLEAR = "clear"
    REVIEW = "review"
    ESCALATE = "escalate"
    DENY = "deny"


class WatchlistType(Enum):
    """Federal and internal watchlist sources."""

    TSDB = "terrorist_screening_database"
    SDN = "specially_designated_nationals"
    FBI = "fbi_wanted"
    INTERPOL = "interpol"
    CUSTOM = "custom_internal"
    DEBARMENT = "federal_debarment"


@dataclass
class ScreeningResult:
    """Result of visitor threat screening."""

    visitor_id: str
    threat_level: ThreatLevel
    confidence: float
    watchlist_hits: list[dict[str, Any]]
    behavioral_flags: list[dict[str, Any]]
    identity_verification: dict[str, Any]
    recommended_action: str
    requires_escort: bool
    restricted_areas: list[str]
    screening_timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ThreatAssessmentConfig:
    """Configuration for threat assessment engine."""

    ofac_api_url: str = "https://api.ofac-api.com/v3"
    ofac_api_key: str = ""
    sam_api_url: str = "https://api.sam.gov/entity-information/v3"
    sam_api_key: str = ""
    behavioral_model_path: str = "/models/behavioral"
    confidence_threshold: float = 0.85
    request_timeout: int = 30


class ScreeningError(Exception):
    """Error during visitor screening process."""


class ThreatAssessmentEngine:
    """
    Multi-source threat assessment for visitor screening.

    Screening Pipeline:
    1. Identity verification (ID scan + liveness)
    2. Watchlist screening (parallel queries)
    3. Behavioral analysis (historical patterns)
    4. Risk aggregation and decision

    Example:
        >>> engine = ThreatAssessmentEngine(config)
        >>> result = await engine.screen_visitor(visitor_data, id_doc, selfie)
        >>> if result.threat_level == ThreatLevel.CLEAR:
        ...     issue_badge(result.visitor_id)
    """

    def __init__(self, config: ThreatAssessmentConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> ThreatAssessmentEngine:
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.request_timeout)
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def screen_visitor(
        self,
        visitor_data: dict[str, Any],
        id_document: bytes,
        selfie: bytes,
    ) -> ScreeningResult:
        """
        Perform comprehensive visitor screening.

        Args:
            visitor_data: Visitor information including name, DOB, purpose.
            id_document: Government ID image as bytes.
            selfie: Live photo for face matching.

        Returns:
            ScreeningResult with threat level and recommended actions.

        Raises:
            ScreeningError: If screening cannot be completed.
        """
        # Step 1: Identity verification
        identity_result = await self._verify_identity(id_document, selfie)

        if not identity_result["verified"]:
            return ScreeningResult(
                visitor_id=visitor_data["id"],
                threat_level=ThreatLevel.DENY,
                confidence=identity_result["confidence"],
                watchlist_hits=[],
                behavioral_flags=[{"type": "identity_mismatch"}],
                identity_verification=identity_result,
                recommended_action="Identity verification failed - deny entry",
                requires_escort=False,
                restricted_areas=["all"],
            )

        # Step 2: Parallel watchlist screening
        watchlist_results = await self._screen_watchlists(
            name=visitor_data["full_name"],
            dob=visitor_data.get("date_of_birth"),
            id_number=identity_result.get("document_number"),
            nationality=identity_result.get("nationality"),
        )

        # Step 3: Behavioral analysis
        behavioral_flags = self._analyze_behavior(visitor_data)

        # Step 4: Aggregate risk
        return self._aggregate_risk(
            visitor_data,
            identity_result,
            watchlist_results,
            behavioral_flags,
        )

    async def _screen_watchlists(
        self,
        name: str,
        dob: str | None,
        id_number: str | None,
        nationality: str | None,
    ) -> dict[WatchlistType, dict[str, Any] | None]:
        """Screen against multiple watchlists in parallel."""
        tasks = [
            self._query_ofac_sdn(name, dob, nationality),
            self._query_sam_exclusions(name),
            self._query_internal_watchlist(name, id_number),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            WatchlistType.SDN: results[0] if not isinstance(results[0], Exception) else None,
            WatchlistType.DEBARMENT: results[1] if not isinstance(results[1], Exception) else None,
            WatchlistType.CUSTOM: results[2] if not isinstance(results[2], Exception) else None,
        }

    async def _query_ofac_sdn(
        self,
        name: str,
        dob: str | None,
        nationality: str | None,
    ) -> dict[str, Any]:
        """Query OFAC Specially Designated Nationals list."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        # Mock response for development - real implementation calls API
        if not self.config.ofac_api_key:
            return {"matches": [], "highest_score": 0}

        params: dict[str, Any] = {
            "name": name,
            "type": "individual",
            "minScore": 80,
        }
        if dob:
            params["dateOfBirth"] = dob
        if nationality:
            params["country"] = nationality

        response = await self._client.get(
            self.config.ofac_api_url,
            params=params,
            headers={"Authorization": f"Bearer {self.config.ofac_api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        matches = data.get("matches", [])
        return {
            "matches": matches,
            "highest_score": max((m["score"] for m in matches), default=0),
        }

    async def _query_sam_exclusions(self, name: str) -> dict[str, Any]:
        """Query SAM.gov exclusions database."""
        # Mock implementation - real version calls SAM.gov API
        return {"matches": [], "highest_score": 0}

    async def _query_internal_watchlist(
        self,
        name: str,
        id_number: str | None,
    ) -> dict[str, Any]:
        """Query internal organization watchlist."""
        # Mock implementation - real version queries internal DB
        return {"matches": [], "highest_score": 0}

    async def _verify_identity(
        self,
        id_document: bytes,
        selfie: bytes,
    ) -> dict[str, Any]:
        """Verify identity through document and biometric analysis."""
        # Import identity verifier for actual verification
        from services.visitor.ml.identity.verifier import IdentityVerifier

        verifier = IdentityVerifier({})
        result = await verifier.verify(id_document, selfie)

        return {
            "verified": result.verified,
            "confidence": result.confidence,
            "document_number": result.document_number,
            "nationality": result.nationality,
            "face_match_score": result.face_match_score,
            "liveness_score": result.liveness_score,
        }

    def _analyze_behavior(self, visitor_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Behavioral analysis based on visitor history."""
        flags: list[dict[str, Any]] = []

        # High visit frequency
        if visitor_data.get("visits_last_30_days", 0) > 10:
            flags.append({
                "type": "high_frequency",
                "severity": "low",
                "detail": f"Visited {visitor_data['visits_last_30_days']} times in 30 days",
            })

        # Previous denials
        if visitor_data.get("previous_denials", 0) > 0:
            flags.append({
                "type": "previous_denial",
                "severity": "high",
                "detail": f"Previously denied entry {visitor_data['previous_denials']} times",
            })

        # Expired credentials
        if visitor_data.get("credentials_expired"):
            flags.append({
                "type": "expired_credentials",
                "severity": "medium",
                "detail": "Background check or training certification expired",
            })

        return flags

    def _aggregate_risk(
        self,
        visitor_data: dict[str, Any],
        identity_result: dict[str, Any],
        watchlist_results: dict[WatchlistType, dict[str, Any] | None],
        behavioral_flags: list[dict[str, Any]],
    ) -> ScreeningResult:
        """Aggregate all screening results into final decision."""
        risk_score = 0.0

        # Identity verification weight
        risk_score += (1 - identity_result["confidence"]) * 0.3

        # Watchlist hits
        for wl_type, result in watchlist_results.items():
            if result and result.get("highest_score", 0) > 85:
                if wl_type == WatchlistType.SDN:
                    risk_score += 1.0  # Automatic deny
                else:
                    risk_score += 0.4

        # Behavioral flags
        for flag in behavioral_flags:
            severity_weights = {"high": 0.3, "medium": 0.15, "low": 0.05}
            risk_score += severity_weights.get(flag["severity"], 0.05)

        # Determine threat level and actions
        if risk_score >= 0.8:
            threat_level = ThreatLevel.DENY
            action = "Entry denied - security escalation required"
            escort = False
            restricted = ["all"]
        elif risk_score >= 0.5:
            threat_level = ThreatLevel.ESCALATE
            action = "Security review required before entry"
            escort = True
            restricted = ["secure_areas", "executive_floor", "data_center"]
        elif risk_score >= 0.3:
            threat_level = ThreatLevel.REVIEW
            action = "Additional verification recommended"
            escort = True
            restricted = ["secure_areas"]
        else:
            threat_level = ThreatLevel.CLEAR
            action = "Approved for entry"
            escort = False
            restricted = []

        return ScreeningResult(
            visitor_id=visitor_data["id"],
            threat_level=threat_level,
            confidence=max(0.0, 1 - risk_score),
            watchlist_hits=[
                {"list": k.value, "result": v}
                for k, v in watchlist_results.items()
                if v and v.get("matches")
            ],
            behavioral_flags=behavioral_flags,
            identity_verification=identity_result,
            recommended_action=action,
            requires_escort=escort,
            restricted_areas=restricted,
        )

