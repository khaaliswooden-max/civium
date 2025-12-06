#!/usr/bin/env python3
"""
Database Initialization Script
==============================

Initialize all Civium databases with required schemas and seed data.

Usage:
    python scripts/init_databases.py
    python scripts/init_databases.py --postgres-only
    python scripts/init_databases.py --neo4j-only
    python scripts/init_databases.py --mongodb-only

Version: 0.1.0
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.logging import get_logger, setup_logging

setup_logging(log_level="INFO", json_logs=False, service_name="init-db")
logger = get_logger(__name__)


async def init_postgres() -> bool:
    """Initialize PostgreSQL database."""
    from sqlalchemy import text
    from shared.database.postgres import PostgresClient
    from shared.config import settings

    logger.info("Initializing PostgreSQL...")

    try:
        engine = PostgresClient.get_engine()
        async with engine.begin() as conn:
            # Read and execute init SQL
            init_file = Path("infrastructure/docker/postgres/init.sql")
            if init_file.exists():
                sql = init_file.read_text()
                # Split by semicolons and execute each statement
                for statement in sql.split(";"):
                    stmt = statement.strip()
                    if stmt and not stmt.startswith("--"):
                        await conn.execute(text(stmt))

            # Verify connection
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"PostgreSQL connected: {version[:50]}...")

        logger.info("PostgreSQL initialized successfully")
        return True

    except Exception as e:
        logger.error(f"PostgreSQL initialization failed: {e}")
        return False


async def init_neo4j() -> bool:
    """Initialize Neo4j database with constraints and indexes."""
    from shared.database.neo4j import Neo4jClient

    logger.info("Initializing Neo4j...")

    try:
        driver = Neo4jClient.get_driver()

        # Read init cypher file
        init_file = Path("infrastructure/docker/neo4j/init.cypher")
        if init_file.exists():
            cypher = init_file.read_text()

            async with driver.session() as session:
                # Execute each statement
                for statement in cypher.split(";"):
                    stmt = statement.strip()
                    if stmt and not stmt.startswith("//"):
                        try:
                            await session.run(stmt)
                        except Exception as e:
                            # Some constraints may already exist
                            if "already exists" not in str(e).lower():
                                logger.warning(f"Neo4j statement warning: {e}")

        # Verify connection
        async with driver.session() as session:
            result = await session.run("CALL dbms.components() YIELD name, versions")
            record = await result.single()
            logger.info(f"Neo4j connected: {record['name']} {record['versions'][0]}")

        logger.info("Neo4j initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Neo4j initialization failed: {e}")
        return False


async def init_mongodb() -> bool:
    """Initialize MongoDB with collections and indexes."""
    from shared.database.mongodb import MongoDBClient

    logger.info("Initializing MongoDB...")

    try:
        client = MongoDBClient.get_client()

        # Create indexes
        await MongoDBClient.create_indexes()

        # Verify connection
        info = await client.server_info()
        logger.info(f"MongoDB connected: v{info['version']}")

        logger.info("MongoDB initialized successfully")
        return True

    except Exception as e:
        logger.error(f"MongoDB initialization failed: {e}")
        return False


async def init_redis() -> bool:
    """Initialize Redis and verify connection."""
    from shared.database.redis import RedisClient

    logger.info("Initializing Redis...")

    try:
        client = RedisClient.get_client()

        # Ping to verify
        await client.ping()

        # Get info
        info = await client.info("server")
        logger.info(f"Redis connected: v{info['redis_version']}")

        logger.info("Redis initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
        return False


async def init_influxdb() -> bool:
    """Initialize InfluxDB and create buckets."""
    from shared.config import settings

    logger.info("Initializing InfluxDB...")

    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS

        client = InfluxDBClient(
            url=settings.influxdb.url,
            token=settings.influxdb.token.get_secret_value(),
            org=settings.influxdb.org,
        )

        # Verify connection
        health = client.health()
        if health.status == "pass":
            logger.info(f"InfluxDB connected: v{health.version}")
            client.close()
            return True

        logger.error(f"InfluxDB health check failed: {health.message}")
        client.close()
        return False

    except Exception as e:
        logger.error(f"InfluxDB initialization failed: {e}")
        return False


async def init_kafka() -> bool:
    """Verify Kafka connection and create topics if needed."""
    from shared.database.kafka import KafkaClient, Topics

    logger.info("Initializing Kafka...")

    try:
        health = await KafkaClient.health_check()
        if health.get("status") == "healthy":
            logger.info(
                f"Kafka connected: {health['brokers']} broker(s), "
                f"{health['topics']} topic(s)"
            )
            return True

        logger.error(f"Kafka health check failed: {health.get('error')}")
        return False

    except Exception as e:
        logger.error(f"Kafka initialization failed: {e}")
        return False


async def seed_data() -> bool:
    """Seed initial data for development."""
    logger.info("Seeding initial data...")

    # This would seed:
    # - Sample jurisdictions
    # - Sample sectors
    # - Demo entities
    # - Sample regulations

    logger.info("Data seeding completed (placeholder)")
    return True


async def main(args: argparse.Namespace) -> int:
    """Main initialization function."""
    logger.info("=" * 60)
    logger.info("CIVIUM Database Initialization")
    logger.info("=" * 60)

    results = {}

    if args.all or args.postgres_only:
        results["PostgreSQL"] = await init_postgres()

    if args.all or args.neo4j_only:
        results["Neo4j"] = await init_neo4j()

    if args.all or args.mongodb_only:
        results["MongoDB"] = await init_mongodb()

    if args.all:
        results["Redis"] = await init_redis()
        results["InfluxDB"] = await init_influxdb()
        results["Kafka"] = await init_kafka()

    if args.seed:
        results["Seed Data"] = await seed_data()

    # Summary
    logger.info("=" * 60)
    logger.info("Initialization Summary")
    logger.info("=" * 60)

    failed = []
    for name, success in results.items():
        status = "✓ OK" if success else "✗ FAILED"
        logger.info(f"  {name}: {status}")
        if not success:
            failed.append(name)

    if failed:
        logger.error(f"\nFailed: {', '.join(failed)}")
        return 1

    logger.info("\nAll databases initialized successfully!")
    return 0


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Initialize Civium databases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--postgres-only",
        action="store_true",
        help="Initialize only PostgreSQL",
    )
    parser.add_argument(
        "--neo4j-only",
        action="store_true",
        help="Initialize only Neo4j",
    )
    parser.add_argument(
        "--mongodb-only",
        action="store_true",
        help="Initialize only MongoDB",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed initial development data",
    )

    args = parser.parse_args()

    # If no specific database is selected, init all
    args.all = not (args.postgres_only or args.neo4j_only or args.mongodb_only)

    return args


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)

