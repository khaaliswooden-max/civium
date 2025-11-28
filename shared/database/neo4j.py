"""
Neo4j Client
============

Async Neo4j driver for the Compliance Graph Engine.

Version: 0.1.0
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from shared.config import settings
from shared.logging import get_logger

logger = get_logger(__name__)


class Neo4jClient:
    """
    Async Neo4j client wrapper.

    Manages driver lifecycle and provides query utilities.
    """

    _driver: AsyncDriver | None = None

    @classmethod
    def get_driver(cls) -> AsyncDriver:
        """Get or create the async driver."""
        if cls._driver is None:
            cls._driver = AsyncGraphDatabase.driver(
                settings.neo4j.uri,
                auth=(
                    settings.neo4j.user,
                    settings.neo4j.password.get_secret_value(),
                ),
                max_connection_pool_size=50,
                connection_acquisition_timeout=30.0,
            )
            logger.info(
                "neo4j_driver_created",
                uri=settings.neo4j.uri,
            )
        return cls._driver

    @classmethod
    async def close(cls) -> None:
        """Close the driver and release all connections."""
        if cls._driver is not None:
            await cls._driver.close()
            cls._driver = None
            logger.info("neo4j_driver_closed")

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
            driver = cls.get_driver()
            async with driver.session() as session:
                result = await session.run("RETURN 1 AS n")
                _ = await result.single()
            latency_ms = (time.perf_counter() - start) * 1000

            # Get server info
            server_info = await driver.get_server_info()

            return {
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
                "server_version": server_info.agent,
                "protocol_version": str(server_info.protocol_version),
            }
        except Exception as e:
            logger.error("neo4j_health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    @classmethod
    async def run_query(
        cls,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str = "neo4j",
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters
            database: Database name (default: neo4j)

        Returns:
            List of result records as dictionaries
        """
        driver = cls.get_driver()
        async with driver.session(database=database) as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    @classmethod
    async def run_write_query(
        cls,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str = "neo4j",
    ) -> dict[str, Any]:
        """
        Execute a write query with transaction.

        Args:
            query: Cypher query string
            parameters: Query parameters
            database: Database name

        Returns:
            Query counters (nodes_created, relationships_created, etc.)
        """
        driver = cls.get_driver()

        async def _write_tx(tx: Any) -> dict[str, Any]:
            result = await tx.run(query, parameters or {})
            summary = await result.consume()
            counters = summary.counters
            return {
                "nodes_created": counters.nodes_created,
                "nodes_deleted": counters.nodes_deleted,
                "relationships_created": counters.relationships_created,
                "relationships_deleted": counters.relationships_deleted,
                "properties_set": counters.properties_set,
                "labels_added": counters.labels_added,
                "labels_removed": counters.labels_removed,
            }

        async with driver.session(database=database) as session:
            return await session.execute_write(_write_tx)


async def get_neo4j_driver() -> AsyncDriver:
    """
    Dependency that provides the Neo4j driver.

    Usage:
        @app.get("/graph")
        async def graph(driver: AsyncDriver = Depends(get_neo4j_driver)):
            async with driver.session() as session:
                ...
    """
    return Neo4jClient.get_driver()


@asynccontextmanager
async def neo4j_session(
    database: str = "neo4j",
) -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for Neo4j sessions.

    Usage:
        async with neo4j_session() as session:
            result = await session.run("MATCH (n) RETURN n LIMIT 10")
    """
    driver = Neo4jClient.get_driver()
    async with driver.session(database=database) as session:
        yield session

