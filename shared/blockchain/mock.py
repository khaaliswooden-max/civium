"""
Mock Blockchain Client
======================

In-memory mock implementation for development and testing.

Version: 0.1.0
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from shared.blockchain.client import (
    AuditEventType,
    AuditRecord,
    BlockchainClient,
    CredentialStatus,
    DID,
    DIDDocument,
    VerifiableCredential,
)
from shared.config import BlockchainMode
from shared.logging import get_logger

logger = get_logger(__name__)


class MockBlockchainClient(BlockchainClient):
    """
    In-memory mock blockchain client.

    Simulates blockchain operations for development without
    requiring actual blockchain infrastructure.

    Data is stored in memory and lost on restart.
    """

    def __init__(self) -> None:
        """Initialize mock client with in-memory storage."""
        self._connected = False
        self._block_number = 1000

        # In-memory storage
        self._audit_records: dict[str, AuditRecord] = {}
        self._dids: dict[str, DID] = {}
        self._credentials: dict[str, VerifiableCredential] = {}

        # Index by entity
        self._entity_audits: dict[str, list[str]] = {}
        self._entity_dids: dict[str, str] = {}

        logger.debug("mock_blockchain_initialized")

    @property
    def mode(self) -> BlockchainMode:
        return BlockchainMode.MOCK

    async def connect(self) -> None:
        """Simulate connection."""
        self._connected = True
        logger.info("mock_blockchain_connected")

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        logger.info("mock_blockchain_disconnected")

    async def health_check(self) -> dict[str, Any]:
        """Check mock blockchain health."""
        return {
            "status": "healthy",
            "mode": self.mode.value,
            "connected": self._connected,
            "block_number": self._block_number,
            "audit_records": len(self._audit_records),
            "dids": len(self._dids),
            "credentials": len(self._credentials),
        }

    def _generate_tx_hash(self) -> str:
        """Generate a mock transaction hash."""
        return "0x" + hashlib.sha256(uuid.uuid4().bytes).hexdigest()

    def _next_block(self) -> int:
        """Get next block number."""
        self._block_number += 1
        return self._block_number

    # =========================================================================
    # Audit Trail
    # =========================================================================

    async def record_audit(
        self,
        entity_id: str,
        event_type: AuditEventType,
        data_hash: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """Record an audit event."""
        # Get previous hash for chain
        previous_hash = None
        if entity_id in self._entity_audits and self._entity_audits[entity_id]:
            last_audit_id = self._entity_audits[entity_id][-1]
            last_audit = self._audit_records[last_audit_id]
            previous_hash = last_audit.data_hash

        # Create record
        audit_id = f"audit:{uuid.uuid4()}"
        tx_hash = self._generate_tx_hash()
        block_number = self._next_block()

        record = AuditRecord(
            id=audit_id,
            entity_id=entity_id,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            data_hash=data_hash,
            previous_hash=previous_hash,
            tx_hash=tx_hash,
            block_number=block_number,
            metadata=metadata or {},
        )

        # Store
        self._audit_records[audit_id] = record

        if entity_id not in self._entity_audits:
            self._entity_audits[entity_id] = []
        self._entity_audits[entity_id].append(audit_id)

        logger.debug(
            "mock_audit_recorded",
            audit_id=audit_id,
            entity_id=entity_id,
            event_type=event_type.value,
            tx_hash=tx_hash,
        )

        return record

    async def get_audit_trail(
        self,
        entity_id: str,
        limit: int = 100,
    ) -> list[AuditRecord]:
        """Get audit trail for an entity."""
        if entity_id not in self._entity_audits:
            return []

        audit_ids = self._entity_audits[entity_id][-limit:]
        records = [self._audit_records[aid] for aid in reversed(audit_ids)]

        return records

    async def verify_audit(self, audit_id: str) -> bool:
        """Verify an audit record."""
        return audit_id in self._audit_records

    # =========================================================================
    # Decentralized Identity
    # =========================================================================

    async def create_did(
        self,
        entity_id: str,
        public_key: str | None = None,
    ) -> DID:
        """Create a new DID."""
        # Check if entity already has DID
        if entity_id in self._entity_dids:
            existing_did = self._dids[self._entity_dids[entity_id]]
            logger.warning(
                "mock_did_already_exists",
                entity_id=entity_id,
                did=existing_did.identifier,
            )
            return existing_did

        # Generate DID identifier
        did_id = f"did:civium:{uuid.uuid4().hex[:16]}"
        tx_hash = self._generate_tx_hash()

        # Create verification method if public key provided
        verification_methods = []
        authentications = []
        if public_key:
            vm_id = f"{did_id}#key-1"
            verification_methods.append({
                "id": vm_id,
                "type": "Ed25519VerificationKey2020",
                "controller": did_id,
                "publicKeyMultibase": public_key,
            })
            authentications.append(vm_id)

        # Create document
        document = DIDDocument(
            id=did_id,
            controller=did_id,
            verification_method=verification_methods,
            authentication=authentications,
            service=[
                {
                    "id": f"{did_id}#civium",
                    "type": "CiviumComplianceService",
                    "serviceEndpoint": f"https://api.civium.io/entities/{entity_id}",
                }
            ],
        )

        # Create DID object
        did = DID(
            identifier=did_id,
            entity_id=entity_id,
            document=document,
            tx_hash=tx_hash,
        )

        # Store
        self._dids[did_id] = did
        self._entity_dids[entity_id] = did_id

        logger.info(
            "mock_did_created",
            did=did_id,
            entity_id=entity_id,
            tx_hash=tx_hash,
        )

        return did

    async def resolve_did(self, did: str) -> DIDDocument | None:
        """Resolve a DID to its document."""
        if did not in self._dids:
            return None
        return self._dids[did].document

    async def update_did(
        self,
        did: str,
        updates: dict[str, Any],
    ) -> DIDDocument:
        """Update a DID document."""
        if did not in self._dids:
            raise ValueError(f"DID not found: {did}")

        did_obj = self._dids[did]
        document = did_obj.document

        # Apply updates
        for key, value in updates.items():
            if hasattr(document, key):
                setattr(document, key, value)

        document.updated = datetime.now(UTC)

        logger.debug("mock_did_updated", did=did)

        return document

    async def deactivate_did(self, did: str) -> bool:
        """Deactivate a DID."""
        if did not in self._dids:
            return False

        self._dids[did].active = False
        logger.info("mock_did_deactivated", did=did)
        return True

    # =========================================================================
    # Verifiable Credentials
    # =========================================================================

    async def issue_credential(
        self,
        issuer_did: str,
        subject_did: str,
        credential_type: str,
        claims: dict[str, Any],
        expiration_days: int | None = None,
    ) -> VerifiableCredential:
        """Issue a verifiable credential."""
        credential_id = f"urn:civium:vc:{uuid.uuid4().hex[:16]}"
        tx_hash = self._generate_tx_hash()
        now = datetime.now(UTC)

        expiration_date = None
        if expiration_days:
            expiration_date = now + timedelta(days=expiration_days)

        credential = VerifiableCredential(
            id=credential_id,
            type=["VerifiableCredential", credential_type],
            issuer=issuer_did,
            issuance_date=now,
            expiration_date=expiration_date,
            credential_subject={
                "id": subject_did,
                **claims,
            },
            proof={
                "type": "Ed25519Signature2020",
                "created": now.isoformat(),
                "verificationMethod": f"{issuer_did}#key-1",
                "proofPurpose": "assertionMethod",
                "proofValue": "mock_signature_" + uuid.uuid4().hex[:32],
            },
            tx_hash=tx_hash,
        )

        self._credentials[credential_id] = credential

        logger.info(
            "mock_credential_issued",
            credential_id=credential_id,
            issuer=issuer_did,
            subject=subject_did,
            type=credential_type,
        )

        return credential

    async def verify_credential(
        self,
        credential_id: str,
    ) -> tuple[bool, str]:
        """Verify a credential."""
        if credential_id not in self._credentials:
            return False, "Credential not found"

        credential = self._credentials[credential_id]

        # Check status
        if credential.status == CredentialStatus.REVOKED:
            return False, "Credential has been revoked"

        if credential.status == CredentialStatus.SUSPENDED:
            return False, "Credential is suspended"

        # Check expiration
        if credential.expiration_date and datetime.now(UTC) > credential.expiration_date:
            return False, "Credential has expired"

        # In mock, always verify signature as valid
        return True, "Credential is valid"

    async def revoke_credential(
        self,
        credential_id: str,
        reason: str,
    ) -> bool:
        """Revoke a credential."""
        if credential_id not in self._credentials:
            return False

        credential = self._credentials[credential_id]
        credential.status = CredentialStatus.REVOKED

        # Record revocation in audit trail
        if credential.credential_subject.get("id"):
            subject_did = credential.credential_subject["id"]
            # Find entity for this DID
            for did_obj in self._dids.values():
                if did_obj.identifier == subject_did:
                    await self.record_audit(
                        entity_id=did_obj.entity_id,
                        event_type=AuditEventType.CREDENTIAL_REVOKED,
                        data_hash=hashlib.sha256(
                            f"{credential_id}:{reason}".encode()
                        ).hexdigest(),
                        metadata={"credential_id": credential_id, "reason": reason},
                    )
                    break

        logger.info(
            "mock_credential_revoked",
            credential_id=credential_id,
            reason=reason,
        )

        return True

    # =========================================================================
    # Test Utilities
    # =========================================================================

    def clear_all(self) -> None:
        """Clear all mock data (for testing)."""
        self._audit_records.clear()
        self._dids.clear()
        self._credentials.clear()
        self._entity_audits.clear()
        self._entity_dids.clear()
        self._block_number = 1000
        logger.debug("mock_blockchain_cleared")

    def get_stats(self) -> dict[str, int]:
        """Get storage statistics."""
        return {
            "audit_records": len(self._audit_records),
            "dids": len(self._dids),
            "credentials": len(self._credentials),
            "block_number": self._block_number,
        }

