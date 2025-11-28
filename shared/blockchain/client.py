"""
Blockchain Client Interface
===========================

Abstract base class and models for blockchain operations.

Version: 0.1.0
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from shared.config import settings, BlockchainMode
from shared.logging import get_logger

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""

    COMPLIANCE_ASSESSMENT = "compliance_assessment"
    SCORE_CHANGE = "score_change"
    TIER_CHANGE = "tier_change"
    REQUIREMENT_UPDATE = "requirement_update"
    VIOLATION_RECORDED = "violation_recorded"
    VERIFICATION_COMPLETED = "verification_completed"
    CREDENTIAL_ISSUED = "credential_issued"
    CREDENTIAL_REVOKED = "credential_revoked"


class AuditRecord(BaseModel):
    """Audit trail record."""

    id: str = Field(..., description="Unique audit record ID")
    entity_id: str = Field(..., description="Entity this audit relates to")
    event_type: AuditEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data_hash: str = Field(..., description="SHA-256 hash of the audit data")
    previous_hash: str | None = Field(default=None, description="Hash of previous record")
    tx_hash: str | None = Field(default=None, description="Blockchain transaction hash")
    block_number: int | None = Field(default=None, description="Block number")

    # Additional metadata
    metadata: dict[str, Any] = Field(default_factory=dict)


class DIDDocument(BaseModel):
    """Decentralized Identifier Document."""

    context: list[str] = Field(
        default=["https://www.w3.org/ns/did/v1"],
        alias="@context",
    )
    id: str = Field(..., description="DID identifier (did:civium:...)")
    controller: str | None = None
    verification_method: list[dict[str, Any]] = Field(default_factory=list)
    authentication: list[str] = Field(default_factory=list)
    assertion_method: list[str] = Field(default_factory=list)
    service: list[dict[str, Any]] = Field(default_factory=list)

    # Timestamps
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DID(BaseModel):
    """Decentralized Identifier."""

    identifier: str = Field(..., description="DID identifier")
    entity_id: str = Field(..., description="Associated entity ID")
    document: DIDDocument
    tx_hash: str | None = None
    active: bool = True


class CredentialStatus(str, Enum):
    """Verifiable Credential status."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class VerifiableCredential(BaseModel):
    """W3C Verifiable Credential."""

    context: list[str] = Field(
        default=[
            "https://www.w3.org/2018/credentials/v1",
            "https://civium.io/credentials/v1",
        ],
        alias="@context",
    )
    id: str = Field(..., description="Credential ID (urn:civium:vc:...)")
    type: list[str] = Field(
        default=["VerifiableCredential", "ComplianceCredential"],
    )
    issuer: str = Field(..., description="Issuer DID")
    issuance_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expiration_date: datetime | None = None

    # Credential subject
    credential_subject: dict[str, Any] = Field(default_factory=dict)

    # Proof (added after signing)
    proof: dict[str, Any] | None = None

    # Status
    status: CredentialStatus = CredentialStatus.ACTIVE
    tx_hash: str | None = None


class BlockchainClient(ABC):
    """
    Abstract base class for blockchain clients.

    Implements the Strategy pattern for different blockchain modes.
    """

    @property
    @abstractmethod
    def mode(self) -> BlockchainMode:
        """Get the blockchain mode."""
        ...

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the blockchain network."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the blockchain network."""
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check blockchain health."""
        ...

    # =========================================================================
    # Audit Trail
    # =========================================================================

    @abstractmethod
    async def record_audit(
        self,
        entity_id: str,
        event_type: AuditEventType,
        data_hash: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """
        Record an audit event to the blockchain.

        Args:
            entity_id: Entity ID this audit relates to
            event_type: Type of audit event
            data_hash: SHA-256 hash of the audit data
            metadata: Additional metadata

        Returns:
            AuditRecord with transaction details
        """
        ...

    @abstractmethod
    async def get_audit_trail(
        self,
        entity_id: str,
        limit: int = 100,
    ) -> list[AuditRecord]:
        """
        Get audit trail for an entity.

        Args:
            entity_id: Entity to get audit trail for
            limit: Maximum records to return

        Returns:
            List of AuditRecords, newest first
        """
        ...

    @abstractmethod
    async def verify_audit(self, audit_id: str) -> bool:
        """
        Verify an audit record exists on blockchain.

        Args:
            audit_id: Audit record ID

        Returns:
            True if verified on blockchain
        """
        ...

    # =========================================================================
    # Decentralized Identity
    # =========================================================================

    @abstractmethod
    async def create_did(
        self,
        entity_id: str,
        public_key: str | None = None,
    ) -> DID:
        """
        Create a new DID for an entity.

        Args:
            entity_id: Entity to create DID for
            public_key: Optional public key for verification

        Returns:
            Created DID
        """
        ...

    @abstractmethod
    async def resolve_did(self, did: str) -> DIDDocument | None:
        """
        Resolve a DID to its document.

        Args:
            did: DID identifier to resolve

        Returns:
            DIDDocument or None if not found
        """
        ...

    @abstractmethod
    async def update_did(
        self,
        did: str,
        updates: dict[str, Any],
    ) -> DIDDocument:
        """
        Update a DID document.

        Args:
            did: DID identifier
            updates: Fields to update

        Returns:
            Updated DIDDocument
        """
        ...

    @abstractmethod
    async def deactivate_did(self, did: str) -> bool:
        """
        Deactivate a DID.

        Args:
            did: DID identifier

        Returns:
            True if deactivated
        """
        ...

    # =========================================================================
    # Verifiable Credentials
    # =========================================================================

    @abstractmethod
    async def issue_credential(
        self,
        issuer_did: str,
        subject_did: str,
        credential_type: str,
        claims: dict[str, Any],
        expiration_days: int | None = None,
    ) -> VerifiableCredential:
        """
        Issue a verifiable credential.

        Args:
            issuer_did: DID of the issuer
            subject_did: DID of the credential subject
            credential_type: Type of credential
            claims: Credential claims/attributes
            expiration_days: Days until expiration

        Returns:
            Issued VerifiableCredential
        """
        ...

    @abstractmethod
    async def verify_credential(
        self,
        credential_id: str,
    ) -> tuple[bool, str]:
        """
        Verify a credential.

        Args:
            credential_id: Credential ID to verify

        Returns:
            Tuple of (is_valid, reason)
        """
        ...

    @abstractmethod
    async def revoke_credential(
        self,
        credential_id: str,
        reason: str,
    ) -> bool:
        """
        Revoke a credential.

        Args:
            credential_id: Credential to revoke
            reason: Reason for revocation

        Returns:
            True if revoked
        """
        ...


# Global client instance
_client: BlockchainClient | None = None


def get_blockchain_client() -> BlockchainClient:
    """
    Get the configured blockchain client instance.

    Returns:
        BlockchainClient instance based on settings
    """
    global _client

    if _client is None:
        mode = settings.blockchain.mode

        if mode == BlockchainMode.MOCK:
            from shared.blockchain.mock import MockBlockchainClient

            _client = MockBlockchainClient()
        elif mode in (BlockchainMode.TESTNET, BlockchainMode.MAINNET):
            # TODO: Implement real blockchain client in Phase 2
            # from shared.blockchain.polygon import PolygonClient
            # _client = PolygonClient()
            raise NotImplementedError(
                f"Blockchain mode '{mode}' not yet implemented. "
                "Use BLOCKCHAIN_MODE=mock for development."
            )
        else:
            raise ValueError(f"Unknown blockchain mode: {mode}")

        logger.info(
            "blockchain_client_initialized",
            mode=mode.value,
        )

    return _client


def set_blockchain_client(client: BlockchainClient) -> None:
    """
    Set a custom blockchain client.

    Args:
        client: BlockchainClient instance
    """
    global _client
    _client = client
    logger.info(
        "blockchain_client_set",
        mode=client.mode.value,
    )


def reset_blockchain_client() -> None:
    """Reset the client to be re-initialized."""
    global _client
    _client = None

