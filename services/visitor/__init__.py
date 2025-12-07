"""
Pro-Visit: Visitor Management & Threat Assessment Module.

This module provides AI-powered visitor screening, identity verification,
and access control for federal agencies and critical infrastructure.

Key Features:
- AI-Powered Pre-Screening with watchlist integration
- Digital Identity Verification with liveness detection
- Real-time threat assessment and behavioral analysis
- SCIF access control and escort requirements
"""

from services.visitor.ml.threat_assessment.engine import (
    ScreeningResult,
    ThreatAssessmentConfig,
    ThreatAssessmentEngine,
    ThreatLevel,
    WatchlistType,
)
from services.visitor.ml.identity.verifier import (
    IdentityVerificationResult,
    IdentityVerifier,
)

__all__ = [
    "ScreeningResult",
    "ThreatAssessmentConfig",
    "ThreatAssessmentEngine",
    "ThreatLevel",
    "WatchlistType",
    "IdentityVerificationResult",
    "IdentityVerifier",
]

