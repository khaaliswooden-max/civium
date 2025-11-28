"""
MongoDB Client
==============

Async MongoDB client using Motor for regulatory documents.

Version: 0.1.0
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from shared.config import settings
from shared.logging import get_logger

logger = get_logger(__name__)


class MongoDBClient:
    """
    Async MongoDB client wrapper.

    Manages client lifecycle and provides database access.
    """

    _client: AsyncIOMotorClient | None = None  # type: ignore[type-arg]

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:  # type: ignore[type-arg]
        """Get or create the async client."""
        if cls._client is None:
            cls._client = AsyncIOMotorClient(
                settings.mongodb.uri,
                maxPoolSize=50,
                minPoolSize=10,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
            logger.info(
                "mongodb_client_created",
                host=settings.mongodb.host,
                database=settings.mongodb.db,
            )
        return cls._client

    @classmethod
    def get_database(cls, name: str | None = None) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
        """
        Get a database instance.

        Args:
            name: Database name (default from settings)

        Returns:
            AsyncIOMotorDatabase instance
        """
        client = cls.get_client()
        db_name = name or settings.mongodb.db
        return client[db_name]

    @classmethod
    async def close(cls) -> None:
        """Close the client and release all connections."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            logger.info("mongodb_client_closed")

    @classmethod
    async def health_check(cls) -> dict[str, Any]:
        """
        Check database health.

        Returns:
            dict with status and server info
        """
        import time

        try:
            start = time.perf_counter()
            client = cls.get_client()
            # Ping the server
            result = await client.admin.command("ping")
            latency_ms = (time.perf_counter() - start) * 1000

            # Get server info
            server_info = await client.admin.command("serverStatus")

            return {
                "status": "healthy" if result.get("ok") == 1 else "unhealthy",
                "latency_ms": round(latency_ms, 2),
                "version": server_info.get("version", "unknown"),
                "uptime_seconds": server_info.get("uptime", 0),
            }
        except Exception as e:
            logger.error("mongodb_health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    @classmethod
    async def create_indexes(cls) -> None:
        """Create indexes for all collections."""
        db = cls.get_database()

        # Regulations collection
        await db.regulations.create_index("jurisdiction")
        await db.regulations.create_index("effective_date")
        await db.regulations.create_index([("name", "text"), ("raw_text", "text")])

        # Requirements collection
        await db.requirements.create_index("regulation_id")
        await db.requirements.create_index("tier")
        await db.requirements.create_index([("natural_language", "text")])

        logger.info("mongodb_indexes_created")


async def get_mongodb() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """
    Dependency that provides the MongoDB database.

    Usage:
        @app.get("/regulations")
        async def regulations(db: AsyncIOMotorDatabase = Depends(get_mongodb)):
            cursor = db.regulations.find({})
            return await cursor.to_list(100)
    """
    return MongoDBClient.get_database()


@asynccontextmanager
async def mongodb_collection(
    collection_name: str,
    database: str | None = None,
) -> AsyncGenerator[Any, None]:
    """
    Context manager for MongoDB collection access.

    Usage:
        async with mongodb_collection("regulations") as collection:
            doc = await collection.find_one({"_id": "REG-GDPR"})
    """
    db = MongoDBClient.get_database(database)
    yield db[collection_name]

