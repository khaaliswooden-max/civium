# ADR-001: Database Selection

## Status
**Accepted** - November 2024

## Context
Civium requires multiple data stores to handle different types of compliance data:
- **Relational data**: Entities, users, assessments with ACID guarantees
- **Graph data**: Compliance requirements, relationships, conflict detection
- **Document data**: Regulatory documents, unstructured text
- **Cache/Session**: Fast access to frequently used data
- **Time-series**: Compliance metrics over time
- **Events**: Compliance event streaming

## Decision

### Primary Databases

| Data Type | Database | Rationale |
|-----------|----------|-----------|
| Relational | **PostgreSQL 16** | Mature, ACID, excellent async drivers, JSON support |
| Graph | **Neo4j 5** | Best-in-class graph queries, Cypher language, GDS algorithms |
| Document | **MongoDB 7** | Flexible schema for regulations, full-text search |
| Cache | **Redis 7** | Industry standard, pub/sub, distributed locks |
| Time-series | **InfluxDB 2** | Purpose-built for metrics, efficient compression |
| Events | **Apache Kafka** | Durability, replay, exactly-once semantics |

### Rejected Alternatives

| Alternative | Reason for Rejection |
|-------------|---------------------|
| JanusGraph | Less mature, smaller ecosystem than Neo4j |
| Amazon DynamoDB | Vendor lock-in, limited query flexibility |
| TimescaleDB | PostgreSQL extension adds complexity |
| Apache Pulsar | Kafka has larger ecosystem, more tooling |

## Consequences

### Positive
- Each database optimized for its use case
- Clear separation of concerns
- Independent scaling of different data stores
- Rich ecosystems and documentation

### Negative
- Operational complexity of managing multiple databases
- Data consistency challenges across stores
- Higher infrastructure costs
- Team needs expertise in multiple systems

### Mitigations
- Docker Compose for local development simplifies setup
- Kubernetes operators for production management
- Event-driven architecture maintains eventual consistency
- Clear data ownership boundaries per service

## Related
- ADR-002: ZK Proof System
- ADR-003: LLM Selection

