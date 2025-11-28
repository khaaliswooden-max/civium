# ADR-004: Blockchain Platform Selection

## Status
**Accepted** - November 2024

## Context
Civium requires blockchain for:
- Immutable audit trails
- Decentralized identity (DIDs)
- Verifiable credentials
- Zero-knowledge proof verification
- Smart contract execution

Key requirements:
- Low transaction costs for high volume
- EVM compatibility for tooling ecosystem
- Sufficient decentralization for trust
- Fast finality (<5 seconds)

## Decision

### Selected: Ethereum L2 - Polygon PoS

**Network progression:**
1. **Development**: Mock blockchain layer
2. **Testing**: Polygon Mumbai (testnet)
3. **Production**: Polygon Mainnet

### Rationale

| Criteria | Polygon | Ethereum L1 | Solana | Avalanche |
|----------|---------|-------------|--------|-----------|
| Gas cost | ~$0.001 | ~$5-50 | ~$0.0001 | ~$0.01 |
| Finality | ~2s | ~12min | ~0.4s | ~2s |
| EVM | ✓ | ✓ | ✗ | ✓ |
| Ecosystem | Large | Largest | Growing | Medium |
| Decentralization | Medium | High | Low | Medium |

### Architecture

```
┌─────────────────────────────────────────┐
│           Civium Services               │
├─────────────────────────────────────────┤
│     BlockchainClient (Abstract)         │
├──────────────┬──────────────┬───────────┤
│ MockClient   │ TestnetClient│ MainnetClient
│ (In-memory)  │ (Mumbai)     │ (Polygon)   │
└──────────────┴──────────────┴───────────┘
```

### Smart Contracts

| Contract | Purpose | Deployment |
|----------|---------|------------|
| `AuditRegistry` | Immutable audit trails | Phase 2 |
| `DIDRegistry` | DID management | Phase 2 |
| `ComplianceVerifier` | ZK proof verification | Phase 2 |
| `CredentialRegistry` | VC status | Phase 2 |

## Mock Layer (Phase 1)

For development, a mock blockchain layer simulates all operations:

```python
class MockBlockchainClient(BlockchainClient):
    # In-memory storage
    _audit_records: dict[str, AuditRecord]
    _dids: dict[str, DID]
    _credentials: dict[str, VerifiableCredential]
    
    # Simulates blockchain behavior
    async def record_audit(...) -> AuditRecord
    async def create_did(...) -> DID
```

## Consequences

### Positive
- Low costs enable high-volume audit trails
- EVM compatibility = large developer ecosystem
- Fast finality improves UX
- Proven security model

### Negative
- Less decentralized than L1
- Bridge risks for L1 interaction
- Polygon-specific dependencies

### Migration Path
If Polygon becomes unsuitable:
1. Smart contracts are portable to any EVM chain
2. Abstract blockchain layer enables provider swap
3. Data can be migrated via replay

## Environment Configuration

```bash
# Development
BLOCKCHAIN_MODE=mock

# Testing
BLOCKCHAIN_MODE=testnet
ALCHEMY_API_KEY=...
POLYGON_RPC_URL=https://polygon-mumbai.g.alchemy.com/v2/...

# Production
BLOCKCHAIN_MODE=mainnet
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/...
```

## Related
- ADR-002: ZK Proof System
- Phase 2, Week 6 implementation

