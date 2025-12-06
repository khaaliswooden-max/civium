"""
PostgreSQL Client
=================

Async PostgreSQL client using SQLAlchemy 2.0 with asyncpg.

Version: 0.1.0
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from shared.config import settings
from shared.logging import get_logger


logger = get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for ORM models."""

    pass


class PostgresClient:
    """
    Async PostgreSQL client wrapper.

    Manages connection pooling and session lifecycle.
    """

    _engine: AsyncEngine | None = None
    _session_factory: async_sessionmaker[AsyncSession] | None = None

    @classmethod
    def get_engine(cls) -> AsyncEngine:
        """Get or create the async engine."""
        if cls._engine is None:
            cls._engine = create_async_engine(
                settings.postgres.async_url,
                echo=settings.debug,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
            logger.info(
                "postgres_engine_created",
                host=settings.postgres.host,
                database=settings.postgres.db,
            )
        return cls._engine

    @classmethod
    def get_session_factory(cls) -> async_sessionmaker[AsyncSession]:
        """Get or create the session factory."""
        if cls._session_factory is None:
            cls._session_factory = async_sessionmaker(
                cls.get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return cls._session_factory

    @classmethod
    async def close(cls) -> None:
        """Close the engine and release all connections."""
        if cls._engine is not None:
            await cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None
            logger.info("postgres_engine_closed")

    @classmethod
    async def health_check(cls) -> dict[str, Any]:
        """
        Check database health.

        Returns:
            dict with status and latency
        """
        import time

        try:
            start = time.perf_counter()
            async with cls.get_session_factory()() as session:
                result = await session.execute(text("SELECT 1"))
                _ = result.scalar()
            latency_ms = (time.perf_counter() - start) * 1000

            return {
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
                "host": settings.postgres.host,
                "database": settings.postgres.db,
            }
        except Exception as e:
            logger.error("postgres_health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
            }


async def get_postgres_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that yields a PostgreSQL session.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_postgres_session)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    session_factory = PostgresClient.get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def postgres_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for PostgreSQL sessions.

    Usage:
        async with postgres_session() as session:
            result = await session.execute(select(Item))
    """
    session_factory = PostgresClient.get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
