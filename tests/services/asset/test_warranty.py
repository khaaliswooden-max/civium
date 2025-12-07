"""Tests for warranty registry."""

import pytest
from datetime import datetime, timedelta

from services.asset.warranty.registry import (
    BlockchainWarrantyRegistry,
    WarrantyRecord,
    ClaimResult,
)


@pytest.fixture
def registry() -> BlockchainWarrantyRegistry:
    """Create warranty registry for testing."""
    return BlockchainWarrantyRegistry()


class TestBlockchainWarrantyRegistry:
    """Tests for BlockchainWarrantyRegistry."""

    @pytest.mark.asyncio
    async def test_register_warranty(self, registry: BlockchainWarrantyRegistry) -> None:
        """Test warranty registration."""
        record = await registry.register_warranty(
            asset_id="AST-001",
            serial_number="SN123456789",
            product_info={"type": "laptop", "manufacturer": "Dell"},
            owner_info={"id": "USR-001", "name": "John Doe"},
            warranty_terms={"duration_days": 365, "coverage": "full"},
        )

        assert isinstance(record, WarrantyRecord)
        assert record.warranty_id.startswith("WRN-")
        assert record.asset_id == "AST-001"
        assert record.serial_number == "SN123456789"
        assert record.current_owner == "USR-001"
        assert record.warranty_end > record.warranty_start
        assert len(record.blockchain_hash) > 0
        assert len(record.transfer_history) == 1

    @pytest.mark.asyncio
    async def test_get_warranty(self, registry: BlockchainWarrantyRegistry) -> None:
        """Test getting a warranty record."""
        # First register
        record = await registry.register_warranty(
            asset_id="AST-002",
            serial_number="SN987654321",
            product_info={"type": "monitor", "manufacturer": "LG"},
            owner_info={"id": "USR-002", "name": "Jane Doe"},
            warranty_terms={"duration_days": 730, "coverage": "standard"},
        )

        # Then retrieve
        retrieved = await registry.get_warranty(record.warranty_id)

        assert retrieved is not None
        assert retrieved.warranty_id == record.warranty_id

    @pytest.mark.asyncio
    async def test_transfer_warranty(self, registry: BlockchainWarrantyRegistry) -> None:
        """Test warranty transfer."""
        # Register warranty
        record = await registry.register_warranty(
            asset_id="AST-003",
            serial_number="SN111222333",
            product_info={"type": "printer", "manufacturer": "HP"},
            owner_info={"id": "USR-003", "name": "Alice"},
            warranty_terms={"duration_days": 365, "coverage": "standard"},
        )

        # Transfer to new owner
        updated = await registry.transfer_warranty(
            warranty_id=record.warranty_id,
            from_owner="USR-003",
            to_owner="USR-004",
        )

        assert updated.current_owner == "USR-004"
        assert len(updated.transfer_history) == 2
        assert updated.transfer_history[-1]["to"] == "USR-004"

    @pytest.mark.asyncio
    async def test_transfer_warranty_invalid_owner(
        self, registry: BlockchainWarrantyRegistry
    ) -> None:
        """Test transfer fails with wrong owner."""
        record = await registry.register_warranty(
            asset_id="AST-004",
            serial_number="SN444555666",
            product_info={"type": "keyboard", "manufacturer": "Logitech"},
            owner_info={"id": "USR-005", "name": "Bob"},
            warranty_terms={"duration_days": 365, "coverage": "standard"},
        )

        with pytest.raises(ValueError, match="ownership mismatch"):
            await registry.transfer_warranty(
                warranty_id=record.warranty_id,
                from_owner="USR-WRONG",
                to_owner="USR-006",
            )

    @pytest.mark.asyncio
    async def test_process_claim_approved(
        self, registry: BlockchainWarrantyRegistry
    ) -> None:
        """Test processing an approved claim."""
        record = await registry.register_warranty(
            asset_id="AST-005",
            serial_number="SN777888999",
            product_info={"type": "mouse", "manufacturer": "Microsoft"},
            owner_info={"id": "USR-007", "name": "Charlie"},
            warranty_terms={"duration_days": 365, "coverage": "full", "product_value": 100},
        )

        claim_data = {
            "claim_id": "CLM-001",
            "claim_type": "repair",
            "issue_description": "Button not working",
            "estimated_cost": 20,
        }

        result = await registry.process_claim(record.warranty_id, claim_data)

        assert isinstance(result, ClaimResult)
        assert result.warranty_id == record.warranty_id
        assert result.status == "approved"
        assert result.fraud_score < 0.5

    @pytest.mark.asyncio
    async def test_process_claim_expired(
        self, registry: BlockchainWarrantyRegistry
    ) -> None:
        """Test processing a claim on expired warranty."""
        # Create warranty with very short duration
        record = await registry.register_warranty(
            asset_id="AST-006",
            serial_number="SN000111222",
            product_info={"type": "cable", "manufacturer": "Generic"},
            owner_info={"id": "USR-008", "name": "Dave"},
            warranty_terms={"duration_days": -1, "coverage": "standard"},  # Already expired
        )

        claim_data = {
            "claim_id": "CLM-002",
            "claim_type": "replacement",
        }

        result = await registry.process_claim(record.warranty_id, claim_data)

        assert result.status == "denied"
        assert "expired" in result.reason.lower()

