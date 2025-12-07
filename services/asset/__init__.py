"""
Pro-Assure: Warranty & Asset Management Module.

Blockchain-based warranty registry with AI-powered fraud detection
and predictive maintenance for asset lifecycle management.

Key Features:
- Blockchain Warranty Registry with immutable records
- AI Claims Intelligence for fraud detection
- Predictive Maintenance with ML-based failure prediction
- Asset Lifecycle Management
"""

from services.asset.warranty.registry import (
    BlockchainWarrantyRegistry,
    ClaimResult,
    WarrantyRecord,
)
from services.asset.ml.fraud.detector import (
    FraudDetector,
    FraudResult,
)

__all__ = [
    "BlockchainWarrantyRegistry",
    "ClaimResult",
    "WarrantyRecord",
    "FraudDetector",
    "FraudResult",
]

