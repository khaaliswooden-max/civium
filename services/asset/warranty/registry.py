"""
Blockchain Warranty Registry.

Immutable warranty records with transfer tracking on Hyperledger Fabric
for tamper-evident asset lifecycle management.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol


class FabricClient(Protocol):
    """Protocol for Hyperledger Fabric client."""

    async def submit_transaction(
        self,
        function: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Submit a transaction to the blockchain."""
        ...

    async def query(
        self,
        function: str,
        *args: Any,
    ) -> dict[str, Any]:
        """Query the blockchain."""
        ...


class FraudModel(Protocol):
    """Protocol for fraud detection model."""

    def predict(
        self,
        claim: dict[str, Any],
        warranty: dict[str, Any],
    ) -> dict[str, Any]:
        """Predict fraud probability for a claim."""
        ...


@dataclass
class WarrantyRecord:
    """Immutable warranty record."""

    warranty_id: str
    asset_id: str
    serial_number: str
    product_type: str
    manufacturer: str
    purchase_date: datetime
    warranty_start: datetime
    warranty_end: datetime
    coverage_type: str
    terms: dict[str, Any]
    current_owner: str
    transfer_history: list[dict[str, Any]] = field(default_factory=list)
    claims_history: list[dict[str, Any]] = field(default_factory=list)
    blockchain_hash: str = ""


@dataclass
class ClaimResult:
    """Result of warranty claim processing."""

    claim_id: str
    warranty_id: str
    status: str  # approved, denied, pending_review
    confidence: float
    fraud_score: float
    reason: str
    recommended_action: str


class MockFabricClient:
    """Mock Hyperledger Fabric client for development."""

    def __init__(self) -> None:
        self._ledger: dict[str, dict[str, Any]] = {}

    async def submit_transaction(
        self,
        function: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Submit a transaction to mock ledger."""
        if function == "registerWarranty":
            warranty_id = args.get("warranty_id", "")
            self._ledger[warranty_id] = args
            return {"status": "success", "txId": f"TX-{warranty_id}"}
        elif function == "updateWarranty":
            warranty_id = args.get("warranty_id", "")
            self._ledger[warranty_id] = args
            return {"status": "success", "txId": f"TX-{warranty_id}-update"}
        return {"status": "unknown_function"}

    async def query(
        self,
        function: str,
        *args: Any,
    ) -> dict[str, Any]:
        """Query mock ledger."""
        if function == "getWarranty" and args:
            warranty_id = args[0]
            return self._ledger.get(warranty_id, {})
        return {}


class MockFraudModel:
    """Mock fraud detection model for development."""

    def predict(
        self,
        claim: dict[str, Any],
        warranty: dict[str, Any],
    ) -> dict[str, Any]:
        """Simple rule-based fraud scoring."""
        score = 0.0

        # Check claim frequency
        claims_count = len(warranty.get("claims_history", []))
        if claims_count > 3:
            score += 0.3

        # Check claim timing (claims near warranty end are suspicious)
        warranty_end = warranty.get("warranty_end")
        if warranty_end:
            if isinstance(warranty_end, str):
                warranty_end = datetime.fromisoformat(warranty_end)
            days_left = (warranty_end - datetime.utcnow()).days
            if 0 < days_left < 30:
                score += 0.2

        # Check claim amount vs product value
        claim_amount = claim.get("estimated_cost", 0)
        product_value = warranty.get("terms", {}).get("product_value", 1000)
        if claim_amount > product_value * 0.8:
            score += 0.2

        return {
            "fraud_score": min(score, 0.99),
            "confidence": 0.85,
            "factors": [],
        }


class BlockchainWarrantyRegistry:
    """
    Immutable Warranty Registry on Hyperledger Fabric.

    Features:
    - Warranty registration and lifecycle tracking
    - Ownership transfer management with full audit trail
    - Claims history recording
    - AI-powered fraud detection integration
    """

    def __init__(
        self,
        fabric_client: FabricClient | None = None,
        fraud_model: FraudModel | None = None,
    ) -> None:
        self.fabric = fabric_client or MockFabricClient()
        self.fraud_model = fraud_model or MockFraudModel()

    async def register_warranty(
        self,
        asset_id: str,
        serial_number: str,
        product_info: dict[str, Any],
        owner_info: dict[str, Any],
        warranty_terms: dict[str, Any],
    ) -> WarrantyRecord:
        """
        Register new warranty on blockchain.

        Args:
            asset_id: Unique asset identifier.
            serial_number: Product serial number.
            product_info: Product details (type, manufacturer).
            owner_info: Owner information.
            warranty_terms: Warranty coverage terms.

        Returns:
            WarrantyRecord with blockchain hash.
        """
        warranty_id = self._generate_warranty_id(serial_number)
        now = datetime.utcnow()

        duration_days = warranty_terms.get("duration_days", 365)

        record = WarrantyRecord(
            warranty_id=warranty_id,
            asset_id=asset_id,
            serial_number=serial_number,
            product_type=product_info.get("type", "unknown"),
            manufacturer=product_info.get("manufacturer", "unknown"),
            purchase_date=now,
            warranty_start=now,
            warranty_end=now + timedelta(days=duration_days),
            coverage_type=warranty_terms.get("coverage", "standard"),
            terms=warranty_terms,
            current_owner=owner_info.get("id", "unknown"),
            transfer_history=[{
                "from": "manufacturer",
                "to": owner_info.get("id", "unknown"),
                "date": now.isoformat(),
                "type": "original_purchase",
            }],
            claims_history=[],
        )

        # Create blockchain hash
        record.blockchain_hash = self._create_hash(record)

        # Submit to blockchain
        await self.fabric.submit_transaction(
            "registerWarranty",
            self._record_to_dict(record),
        )

        return record

    async def transfer_warranty(
        self,
        warranty_id: str,
        from_owner: str,
        to_owner: str,
        transfer_date: datetime | None = None,
    ) -> WarrantyRecord:
        """
        Transfer warranty to new owner.

        Args:
            warranty_id: Warranty identifier.
            from_owner: Current owner ID.
            to_owner: New owner ID.
            transfer_date: Date of transfer (defaults to now).

        Returns:
            Updated WarrantyRecord.

        Raises:
            ValueError: If ownership verification fails.
        """
        if transfer_date is None:
            transfer_date = datetime.utcnow()

        # Get current record
        record = await self.fabric.query("getWarranty", warranty_id)

        if not record:
            raise ValueError(f"Warranty {warranty_id} not found")

        # Verify ownership
        if record.get("current_owner") != from_owner:
            raise ValueError("Transfer not authorized - ownership mismatch")

        # Add transfer record
        transfer = {
            "from": from_owner,
            "to": to_owner,
            "date": transfer_date.isoformat(),
            "type": "ownership_transfer",
        }
        if "transfer_history" not in record:
            record["transfer_history"] = []
        record["transfer_history"].append(transfer)
        record["current_owner"] = to_owner

        # Update blockchain
        await self.fabric.submit_transaction("updateWarranty", record)

        return self._dict_to_record(record)

    async def process_claim(
        self,
        warranty_id: str,
        claim_data: dict[str, Any],
    ) -> ClaimResult:
        """
        Process warranty claim with AI fraud detection.

        Args:
            warranty_id: Warranty identifier.
            claim_data: Claim details.

        Returns:
            ClaimResult with approval status and fraud analysis.
        """
        # Get warranty record
        record = await self.fabric.query("getWarranty", warranty_id)

        if not record:
            return ClaimResult(
                claim_id=claim_data.get("claim_id", "UNKNOWN"),
                warranty_id=warranty_id,
                status="denied",
                confidence=1.0,
                fraud_score=0.0,
                reason="Warranty not found",
                recommended_action="Verify warranty ID",
            )

        # Verify warranty is active
        warranty_end_str = record.get("warranty_end", "")
        if warranty_end_str:
            warranty_end = datetime.fromisoformat(warranty_end_str)
            if warranty_end < datetime.utcnow():
                return ClaimResult(
                    claim_id=claim_data.get("claim_id", "UNKNOWN"),
                    warranty_id=warranty_id,
                    status="denied",
                    confidence=1.0,
                    fraud_score=0.0,
                    reason="Warranty expired",
                    recommended_action="Inform customer of out-of-warranty options",
                )

        # Run fraud detection
        fraud_result = self.fraud_model.predict(claim_data, record)

        if fraud_result["fraud_score"] > 0.8:
            status = "denied"
            reason = "Claim flagged for potential fraud"
            action = "Escalate to fraud investigation team"
        elif fraud_result["fraud_score"] > 0.5:
            status = "pending_review"
            reason = "Claim requires manual review"
            action = "Assign to claims specialist for review"
        else:
            status = "approved"
            reason = "Claim approved - within warranty terms"
            action = "Process replacement/repair per warranty terms"

        # Record claim on blockchain
        claim_record = {
            "claim_id": claim_data.get("claim_id", f"CLM-{datetime.utcnow().timestamp()}"),
            "date": datetime.utcnow().isoformat(),
            "type": claim_data.get("claim_type", "general"),
            "status": status,
            "fraud_score": fraud_result["fraud_score"],
        }
        if "claims_history" not in record:
            record["claims_history"] = []
        record["claims_history"].append(claim_record)
        await self.fabric.submit_transaction("updateWarranty", record)

        return ClaimResult(
            claim_id=claim_record["claim_id"],
            warranty_id=warranty_id,
            status=status,
            confidence=fraud_result["confidence"],
            fraud_score=fraud_result["fraud_score"],
            reason=reason,
            recommended_action=action,
        )

    async def get_warranty(self, warranty_id: str) -> WarrantyRecord | None:
        """Get warranty record by ID."""
        record = await self.fabric.query("getWarranty", warranty_id)
        if record:
            return self._dict_to_record(record)
        return None

    def _generate_warranty_id(self, serial_number: str) -> str:
        """Generate unique warranty ID."""
        timestamp = datetime.utcnow().isoformat()
        data = f"{serial_number}:{timestamp}"
        return f"WRN-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

    def _create_hash(self, record: WarrantyRecord) -> str:
        """Create blockchain hash for record."""
        data = {
            "warranty_id": record.warranty_id,
            "serial_number": record.serial_number,
            "warranty_start": record.warranty_start.isoformat(),
            "warranty_end": record.warranty_end.isoformat(),
            "owner": record.current_owner,
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    def _record_to_dict(self, record: WarrantyRecord) -> dict[str, Any]:
        """Convert WarrantyRecord to dictionary for blockchain."""
        return {
            "warranty_id": record.warranty_id,
            "asset_id": record.asset_id,
            "serial_number": record.serial_number,
            "product_type": record.product_type,
            "manufacturer": record.manufacturer,
            "purchase_date": record.purchase_date.isoformat(),
            "warranty_start": record.warranty_start.isoformat(),
            "warranty_end": record.warranty_end.isoformat(),
            "coverage_type": record.coverage_type,
            "terms": record.terms,
            "current_owner": record.current_owner,
            "transfer_history": record.transfer_history,
            "claims_history": record.claims_history,
            "blockchain_hash": record.blockchain_hash,
        }

    def _dict_to_record(self, data: dict[str, Any]) -> WarrantyRecord:
        """Convert dictionary to WarrantyRecord."""
        return WarrantyRecord(
            warranty_id=data.get("warranty_id", ""),
            asset_id=data.get("asset_id", ""),
            serial_number=data.get("serial_number", ""),
            product_type=data.get("product_type", ""),
            manufacturer=data.get("manufacturer", ""),
            purchase_date=datetime.fromisoformat(data["purchase_date"]) if data.get("purchase_date") else datetime.utcnow(),
            warranty_start=datetime.fromisoformat(data["warranty_start"]) if data.get("warranty_start") else datetime.utcnow(),
            warranty_end=datetime.fromisoformat(data["warranty_end"]) if data.get("warranty_end") else datetime.utcnow(),
            coverage_type=data.get("coverage_type", "standard"),
            terms=data.get("terms", {}),
            current_owner=data.get("current_owner", ""),
            transfer_history=data.get("transfer_history", []),
            claims_history=data.get("claims_history", []),
            blockchain_hash=data.get("blockchain_hash", ""),
        )

