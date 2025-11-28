"""
Blockchain Module
=================

Abstraction layer for blockchain operations.

Supports:
- Mock (development/testing)
- Testnet (Polygon Mumbai)
- Mainnet (Polygon)

Features:
- Audit trail recording
- Decentralized Identity (DID) management
- Verifiable Credentials
- Zero-knowledge proof verification

Usage:
    from shared.blockchain import (
        get_blockchain_client,
        AuditRecord,
        DID,
    )
    
    client = get_blockchain_client()
    
    # Record audit trail
    tx_hash = await client.record_audit(
        entity_id="LEI-123",
        event_type="compliance_assessment",
        data_hash="sha256:...",
    )
    
    # Create DID
    did = await client.create_did(entity_id="LEI-123")
"""

from shared.blockchain.client import (
    BlockchainClient,
    AuditRecord,
    DID,
    VerifiableCredential,
    get_blockchain_client,
    set_blockchain_client,
)
from shared.blockchain.mock import MockBlockchainClient

__all__ = [
    # Client
    "BlockchainClient",
    "get_blockchain_client",
    "set_blockchain_client",
    # Models
    "AuditRecord",
    "DID",
    "VerifiableCredential",
    # Implementations
    "MockBlockchainClient",
]

