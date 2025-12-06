"""
Verification Service Routes
===========================

API route handlers for the verification service.
"""

from services.verification.routes import audit, credentials, proofs, verification


__all__ = ["audit", "credentials", "proofs", "verification"]
