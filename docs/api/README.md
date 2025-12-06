# Civium API Documentation

## Overview

Civium provides a comprehensive REST API for compliance management. All services expose their APIs under `/api/v1/`.

## Base URLs

| Environment | URL |
|-------------|-----|
| Development | `http://localhost:800X` (see service ports below) |
| Staging | `https://api.staging.civium.io` |
| Production | `https://api.civium.io` |

## Service Ports (Development)

| Service | Port | Description |
|---------|------|-------------|
| API Gateway | 8000 | Unified entry point |
| Regulatory Intelligence | 8001 | Regulation parsing and ingestion |
| Compliance Graph | 8002 | Knowledge graph operations |
| Entity Assessment | 8003 | Entity management and scoring |
| Verification | 8004 | ZK proofs and credentials |
| Monitoring | 8005 | Events, alerts, and metrics |

## Authentication

All API requests require a Bearer token in the Authorization header:

```http
Authorization: Bearer <jwt_token>
```

### Obtaining a Token

```http
POST /api/v1/auth/token
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your_password"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

## Common Response Format

All responses follow a consistent format:

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "page": 1,
    "limit": 50,
    "total": 100
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message",
  "status_code": 400,
  "details": { ... }
}
```

## Rate Limiting

Default limits:
- 100 requests per minute
- Burst: 20 requests

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699900000
```

## API Reference

### Regulatory Intelligence Service

- [Regulations API](./regulatory-intelligence.md#regulations)
- [Requirements API](./regulatory-intelligence.md#requirements)
- [Ingestion API](./regulatory-intelligence.md#ingestion)

### Compliance Graph Service

- [Graph Operations](./compliance-graph.md#graph)
- [Entity Graph](./compliance-graph.md#entities)
- [Compliance Status](./compliance-graph.md#compliance)
- [Conflict Detection](./compliance-graph.md#conflicts)

### Entity Assessment Service

- [Entities API](./entity-assessment.md#entities)
- [Assessments API](./entity-assessment.md#assessments)
- [Scores API](./entity-assessment.md#scores)
- [Tiers API](./entity-assessment.md#tiers)

### Verification Service

- [ZK Proofs API](./verification.md#proofs)
- [Verification API](./verification.md#verify)
- [Audit Trail API](./verification.md#audit)
- [Credentials API](./verification.md#credentials)

### Monitoring Service

- [Events API](./monitoring.md#events)
- [Alerts API](./monitoring.md#alerts)
- [Metrics API](./monitoring.md#metrics)
- [Streams API](./monitoring.md#streams)

## OpenAPI Specifications

Interactive API documentation is available at:
- Development: `http://localhost:800X/docs` (Swagger UI)
- Development: `http://localhost:800X/redoc` (ReDoc)

## SDKs

Coming soon:
- Python SDK
- TypeScript/JavaScript SDK
- Go SDK

