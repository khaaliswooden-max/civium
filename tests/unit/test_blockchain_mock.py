"""
Unit tests for mock blockchain client.
"""

import pytest

from shared.blockchain import MockBlockchainClient, AuditRecord
from shared.blockchain.client import AuditEventType, CredentialStatus
from shared.config import BlockchainMode


class TestMockBlockchainClient:
    """Tests for MockBlockchainClient."""

    @pytest.fixture
    def client(self) -> MockBlockchainClient:
        """Create a fresh mock client for each test."""
        client = MockBlockchainClient()
        client.clear_all()
        return client

    def test_client_mode(self, client: MockBlockchainClient) -> None:
        """Test that client reports mock mode."""
        assert client.mode == BlockchainMode.MOCK

    @pytest.mark.asyncio
    async def test_record_audit(self, client: MockBlockchainClient) -> None:
        """Test recording an audit event."""
        record = await client.record_audit(
            entity_id="entity-123",
            event_type=AuditEventType.COMPLIANCE_ASSESSMENT,
            data_hash="sha256:abc123",
            metadata={"score": 4.5},
        )

        assert record.entity_id == "entity-123"
        assert record.event_type == AuditEventType.COMPLIANCE_ASSESSMENT
        assert record.data_hash == "sha256:abc123"
        assert record.tx_hash is not None
        assert record.tx_hash.startswith("0x")
        assert record.block_number is not None
        assert record.metadata["score"] == 4.5

    @pytest.mark.asyncio
    async def test_audit_chain(self, client: MockBlockchainClient) -> None:
        """Test that audit records form a chain."""
        record1 = await client.record_audit(
            entity_id="entity-123",
            event_type=AuditEventType.COMPLIANCE_ASSESSMENT,
            data_hash="hash1",
        )

        record2 = await client.record_audit(
            entity_id="entity-123",
            event_type=AuditEventType.SCORE_CHANGE,
            data_hash="hash2",
        )

        assert record1.previous_hash is None
        assert record2.previous_hash == "hash1"

    @pytest.mark.asyncio
    async def test_get_audit_trail(self, client: MockBlockchainClient) -> None:
        """Test retrieving audit trail."""
        # Record multiple audits
        for i in range(5):
            await client.record_audit(
                entity_id="entity-123",
                event_type=AuditEventType.COMPLIANCE_ASSESSMENT,
                data_hash=f"hash{i}",
            )

        trail = await client.get_audit_trail("entity-123", limit=3)

        assert len(trail) == 3
        # Should be newest first
        assert trail[0].data_hash == "hash4"

    @pytest.mark.asyncio
    async def test_verify_audit(self, client: MockBlockchainClient) -> None:
        """Test audit verification."""
        record = await client.record_audit(
            entity_id="entity-123",
            event_type=AuditEventType.COMPLIANCE_ASSESSMENT,
            data_hash="hash",
        )

        assert await client.verify_audit(record.id) is True
        assert await client.verify_audit("nonexistent") is False

    @pytest.mark.asyncio
    async def test_create_did(self, client: MockBlockchainClient) -> None:
        """Test DID creation."""
        did = await client.create_did(
            entity_id="entity-123",
            public_key="pk_test_123",
        )

        assert did.identifier.startswith("did:civium:")
        assert did.entity_id == "entity-123"
        assert did.active is True
        assert did.tx_hash is not None
        assert len(did.document.verification_method) > 0

    @pytest.mark.asyncio
    async def test_create_did_duplicate(self, client: MockBlockchainClient) -> None:
        """Test that creating DID for same entity returns existing."""
        did1 = await client.create_did(entity_id="entity-123")
        did2 = await client.create_did(entity_id="entity-123")

        assert did1.identifier == did2.identifier

    @pytest.mark.asyncio
    async def test_resolve_did(self, client: MockBlockchainClient) -> None:
        """Test DID resolution."""
        did = await client.create_did(entity_id="entity-123")

        document = await client.resolve_did(did.identifier)

        assert document is not None
        assert document.id == did.identifier

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_did(self, client: MockBlockchainClient) -> None:
        """Test resolving nonexistent DID."""
        document = await client.resolve_did("did:civium:nonexistent")
        assert document is None

    @pytest.mark.asyncio
    async def test_deactivate_did(self, client: MockBlockchainClient) -> None:
        """Test DID deactivation."""
        did = await client.create_did(entity_id="entity-123")

        result = await client.deactivate_did(did.identifier)

        assert result is True
        # Verify it's deactivated
        client_did = client._dids[did.identifier]
        assert client_did.active is False

    @pytest.mark.asyncio
    async def test_issue_credential(self, client: MockBlockchainClient) -> None:
        """Test credential issuance."""
        issuer = await client.create_did(entity_id="issuer")
        subject = await client.create_did(entity_id="subject")

        credential = await client.issue_credential(
            issuer_did=issuer.identifier,
            subject_did=subject.identifier,
            credential_type="ComplianceCertificate",
            claims={"score": 4.5, "tier": "advanced"},
            expiration_days=365,
        )

        assert credential.id.startswith("urn:civium:vc:")
        assert credential.issuer == issuer.identifier
        assert credential.credential_subject["id"] == subject.identifier
        assert credential.credential_subject["score"] == 4.5
        assert credential.status == CredentialStatus.ACTIVE
        assert credential.proof is not None

    @pytest.mark.asyncio
    async def test_verify_credential(self, client: MockBlockchainClient) -> None:
        """Test credential verification."""
        issuer = await client.create_did(entity_id="issuer")
        subject = await client.create_did(entity_id="subject")

        credential = await client.issue_credential(
            issuer_did=issuer.identifier,
            subject_did=subject.identifier,
            credential_type="ComplianceCertificate",
            claims={"score": 4.5},
        )

        is_valid, reason = await client.verify_credential(credential.id)

        assert is_valid is True
        assert reason == "Credential is valid"

    @pytest.mark.asyncio
    async def test_revoke_credential(self, client: MockBlockchainClient) -> None:
        """Test credential revocation."""
        issuer = await client.create_did(entity_id="issuer")
        subject = await client.create_did(entity_id="subject")

        credential = await client.issue_credential(
            issuer_did=issuer.identifier,
            subject_did=subject.identifier,
            credential_type="ComplianceCertificate",
            claims={},
        )

        result = await client.revoke_credential(credential.id, "Test revocation")

        assert result is True

        is_valid, reason = await client.verify_credential(credential.id)
        assert is_valid is False
        assert "revoked" in reason.lower()

    @pytest.mark.asyncio
    async def test_health_check(self, client: MockBlockchainClient) -> None:
        """Test health check."""
        health = await client.health_check()

        assert health["status"] == "healthy"
        assert health["mode"] == "mock"
        assert "block_number" in health

    @pytest.mark.asyncio
    async def test_stats(self, client: MockBlockchainClient) -> None:
        """Test getting stats."""
        await client.record_audit(
            entity_id="e1",
            event_type=AuditEventType.COMPLIANCE_ASSESSMENT,
            data_hash="h1",
        )
        await client.create_did(entity_id="e1")

        stats = client.get_stats()

        assert stats["audit_records"] == 1
        assert stats["dids"] == 1
        assert stats["credentials"] == 0

