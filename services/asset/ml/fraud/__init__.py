"""Fraud detection models."""

from services.asset.ml.fraud.detector import (
    FraudDetector,
    FraudResult,
)

__all__ = [
    "FraudDetector",
    "FraudResult",
]

