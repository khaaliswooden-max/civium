# ADR-005: Inter-Service Communication Patterns

## Status
**Accepted** - November 2024

## Context
Civium's microservices architecture requires clear communication patterns:
- Service-to-service calls
- External API exposure
- Event-driven updates
- Real-time notifications

Key requirements:
- Type safety across service boundaries
- Efficient for high-throughput operations
- Flexible querying for frontend
- Event replay capability

## Decision

### Communication Matrix

| Pattern | Use Case | Technology |
|---------|----------|------------|
| **Sync API** | External clients | REST + GraphQL |
| **Internal RPC** | Service-to-service | gRPC |
| **Events** | Async updates | Kafka |
| **Cache** | Shared state | Redis |

### External APIs: REST + GraphQL

**REST (OpenAPI 3.0)**
- Simple CRUD operations
- Health checks
- Webhook endpoints
- Backwards compatibility

**GraphQL (Apollo Server)**
- Complex queries across services
- Frontend flexibility
- Real-time subscriptions

```
                    ┌──────────────┐
                    │  API Gateway │
                    │ (Kong/Apollo)│
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  REST API     │  │  GraphQL API  │  │  WebSocket    │
│  /api/v1/*    │  │  /graphql     │  │  /ws          │
└───────────────┘  └───────────────┘  └───────────────┘
```

### Internal: gRPC

- Service-to-service calls within cluster
- Protocol Buffers for schema
- Streaming for large data transfers
- Built-in load balancing

### Events: Kafka

**Topics:**
- `civium.compliance.events` - Compliance state changes
- `civium.regulatory.changes` - Regulation updates
- `civium.entity.updates` - Entity modifications
- `civium.audit.logs` - Audit trail

**Guarantees:**
- At-least-once delivery
- Ordered within partition
- 7-day retention
- Schema registry for versioning

## Rejected Alternatives

| Alternative | Reason for Rejection |
|-------------|---------------------|
| REST only | Inefficient for complex queries |
| GraphQL only | Overkill for simple operations |
| RabbitMQ | Kafka better for event replay |
| WebSocket only | Not suitable for request-response |

## Consequences

### Positive
- Right tool for each use case
- Type safety with protobuf/GraphQL schemas
- Event replay for debugging/recovery
- Flexible client access patterns

### Negative
- Multiple protocols to maintain
- Team needs diverse skills
- Schema synchronization overhead

## Implementation Details

### REST Endpoints (FastAPI)
```python
@app.get("/api/v1/entities/{entity_id}")
async def get_entity(entity_id: str) -> Entity:
    ...
```

### GraphQL Schema
```graphql
type Entity {
  id: ID!
  name: String!
  complianceScore: Float
  requirements: [Requirement!]!
}

type Query {
  entity(id: ID!): Entity
  entities(filter: EntityFilter): [Entity!]!
}
```

### Kafka Event
```json
{
  "event_id": "evt_123",
  "event_type": "compliance.score_changed",
  "entity_id": "ent_456",
  "timestamp": "2024-11-28T10:00:00Z",
  "data": {
    "old_score": 3.5,
    "new_score": 4.2
  }
}
```

## Related
- API Gateway configuration
- Service discovery (Kubernetes)
- Event sourcing patterns

