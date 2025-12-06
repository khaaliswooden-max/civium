# Verification Service API

The Verification Service provides ZK-SNARK proof generation, verification, audit trails, and verifiable credentials.

**Base URL:** `/api/v1`

## ZK Proofs {#proofs}

### Generate Threshold Proof

Generate a proof that an entity's score meets or exceeds a threshold.

```http
POST /proofs/threshold
```

**Request Body:**
```json
{
  "entity_id": "LEI-549300EXAMPLE",
  "score": 8500,
  "threshold": 8000
}
```

**Response:**
```json
{
  "success": true,
  "proof_id": "proof-abc123...",
  "proof_type": "threshold",
  "proof": {
    "pi_a": ["123...", "456..."],
    "pi_b": [["789...", "012..."], ["345...", "678..."]],
    "pi_c": ["901...", "234..."],
    "protocol": "groth16",
    "curve": "bn128"
  },
  "public_signals": ["8000", "hash...", "commitment..."],
  "proving_time_ms": 1234,
  "entity_hash": "abc123..."
}
```

### Generate Range Proof

Prove that a score falls within a specific range.

```http
POST /proofs/range
```

**Request Body:**
```json
{
  "entity_id": "LEI-549300EXAMPLE",
  "score": 8500,
  "min_score": 7000,
  "max_score": 9000
}
```

### Generate Tier Proof

Prove membership in a specific compliance tier.

```http
POST /proofs/tier
```

**Request Body:**
```json
{
  "entity_id": "LEI-549300EXAMPLE",
  "score": 9500,
  "tier": 1
}
```

**Tier Definitions:**
| Tier | Score Range | Description |
|------|------------|-------------|
| 1 | 9500-10000 | Exemplary |
| 2 | 8500-9499 | Strong |
| 3 | 7000-8499 | Adequate |
| 4 | 5000-6999 | Developing |
| 5 | 0-4999 | Non-Compliant |

## Verification {#verify}

### Verify Proof

Verify a zero-knowledge proof.

```http
POST /verify/proof
```

**Request Body:**
```json
{
  "proof": { ... },
  "public_signals": ["..."],
  "circuit_name": "compliance_threshold"
}
```

**Response:**
```json
{
  "valid": true,
  "circuit_name": "compliance_threshold",
  "verification_time_ms": 45,
  "public_signals": ["..."],
  "message": "Proof is valid"
}
```

### Batch Verification

Verify multiple proofs efficiently.

```http
POST /verify/batch
```

**Request Body:**
```json
{
  "proofs": [
    {
      "proof": { ... },
      "public_signals": ["..."],
      "circuit_name": "compliance_threshold"
    }
  ]
}
```

## Audit Trail {#audit}

### Create Audit Entry

Record an action in the audit trail.

```http
POST /audit/
```

**Request Body:**
```json
{
  "entity_id": "LEI-549300EXAMPLE",
  "action": "assessment_completed",
  "data": {
    "assessment_id": "...",
    "score": 8500
  },
  "proof_id": "proof-abc123"
}
```

**Response:**
```json
{
  "success": true,
  "entry_id": "uuid...",
  "data_hash": "sha256...",
  "transaction_hash": "0x..."
}
```

### Get Entity Audit Trail

```http
GET /audit/entity/{entity_id}?limit=50&offset=0
```

## Verifiable Credentials {#credentials}

### Issue Credential

Issue a W3C Verifiable Credential.

```http
POST /credentials/issue
```

**Request Body:**
```json
{
  "entity_id": "LEI-549300EXAMPLE",
  "credential_type": "ComplianceAttestation",
  "claims": {
    "tier": 2,
    "jurisdiction": "US",
    "validFrom": "2024-01-01"
  },
  "expiration_days": 365,
  "proof_id": "proof-abc123"
}
```

**Response:**
```json
{
  "success": true,
  "credential_id": "urn:uuid:...",
  "credential": {
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "id": "urn:uuid:...",
    "type": ["VerifiableCredential", "ComplianceAttestation"],
    "issuer": "did:civium:issuer",
    "issuanceDate": "2024-01-01T00:00:00Z",
    "expirationDate": "2025-01-01T00:00:00Z",
    "credentialSubject": {
      "id": "did:civium:LEI-549300EXAMPLE",
      "tier": 2
    },
    "proof": { ... }
  }
}
```

### Verify Credential

```http
POST /credentials/verify
```

**Request Body:**
```json
{
  "credential": { ... }
}
```

### Revoke Credential

```http
POST /credentials/{credential_id}/revoke?reason=...
```

