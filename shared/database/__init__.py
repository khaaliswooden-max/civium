"""
Database Module
===============

Async database clients for all Civium data stores.

Clients:
- PostgreSQL (asyncpg + SQLAlchemy)
- Neo4j (async driver)
- MongoDB (motor)
- Redis (aioredis)
- InfluxDB (influxdb-client)
- Kafka (aiokafka)

Usage:
    from shared.database import (
        get_postgres_session,
        get_neo4j_driver,
        get_mongodb,
        get_redis,
    )
    
    # In FastAPI
    @app.get("/example")
    async def example(
        db: AsyncSession = Depends(get_postgres_session),
    ):
        result = await db.execute(select(Entity))
        ...
"""

from shared.database.postgres import (
    get_postgres_session,
    PostgresClient,
    Base,
)
from shared.database.neo4j import (
    get_neo4j_driver,
    Neo4jClient,
)
from shared.database.mongodb import (
    get_mongodb,
    MongoDBClient,
)
from shared.database.redis import (
    get_redis,
    RedisClient,
)
from shared.database.kafka import (
    get_kafka_producer,
    get_kafka_consumer,
    KafkaClient,
)

__all__ = [
    # PostgreSQL
    "get_postgres_session",
    "PostgresClient",
    "Base",
    # Neo4j
    "get_neo4j_driver",
    "Neo4jClient",
    # MongoDB
    "get_mongodb",
    "MongoDBClient",
    # Redis
    "get_redis",
    "RedisClient",
    # Kafka
    "get_kafka_producer",
    "get_kafka_consumer",
    "KafkaClient",
]

