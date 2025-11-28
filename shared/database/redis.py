"""
Redis Client
============

Async Redis client for caching and session management.

Version: 0.1.0
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis

from shared.config import settings
from shared.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    """
    Async Redis client wrapper.

    Provides caching utilities and connection management.
    """

    _client: Redis | None = None  # type: ignore[type-arg]

    @classmethod
    def get_client(cls) -> Redis:  # type: ignore[type-arg]
        """Get or create the async client."""
        if cls._client is None:
            cls._client = aioredis.from_url(
                settings.redis.url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )
            logger.info(
                "redis_client_created",
                host=settings.redis.host,
            )
        return cls._client

    @classmethod
    async def close(cls) -> None:
        """Close the client and release all connections."""
        if cls._client is not None:
            await cls._client.close()
            cls._client = None
            logger.info("redis_client_closed")

    @classmethod
    async def health_check(cls) -> dict[str, Any]:
        """
        Check Redis health.

        Returns:
            dict with status and server info
        """
        import time

        try:
            start = time.perf_counter()
            client = cls.get_client()
            pong = await client.ping()
            latency_ms = (time.perf_counter() - start) * 1000

            # Get server info
            info = await client.info("server")

            return {
                "status": "healthy" if pong else "unhealthy",
                "latency_ms": round(latency_ms, 2),
                "redis_version": info.get("redis_version", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
            }
        except Exception as e:
            logger.error("redis_health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    # =========================================================================
    # Caching Utilities
    # =========================================================================

    @classmethod
    async def get_cached(
        cls,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a cached value.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        import json

        client = cls.get_client()
        value = await client.get(key)

        if value is None:
            return default

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    @classmethod
    async def set_cached(
        cls,
        key: str,
        value: Any,
        ttl_seconds: int = 3600,
    ) -> bool:
        """
        Set a cached value.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Time to live in seconds

        Returns:
            True if successful
        """
        import json

        client = cls.get_client()

        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        return await client.setex(key, ttl_seconds, value)

    @classmethod
    async def delete_cached(cls, key: str) -> bool:
        """Delete a cached value."""
        client = cls.get_client()
        return await client.delete(key) > 0

    @classmethod
    async def delete_pattern(cls, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "entity:*")

        Returns:
            Number of keys deleted
        """
        client = cls.get_client()
        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            return await client.delete(*keys)
        return 0

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    @classmethod
    async def check_rate_limit(
        cls,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Check and update rate limit.

        Args:
            key: Rate limit key (e.g., "rate:user:123")
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            Tuple of (allowed: bool, remaining: int)
        """
        client = cls.get_client()

        # Use sliding window counter
        current = await client.incr(key)

        if current == 1:
            await client.expire(key, window_seconds)

        remaining = max(0, max_requests - current)
        allowed = current <= max_requests

        return allowed, remaining


async def get_redis() -> Redis:  # type: ignore[type-arg]
    """
    Dependency that provides the Redis client.

    Usage:
        @app.get("/data")
        async def data(redis: Redis = Depends(get_redis)):
            value = await redis.get("key")
    """
    return RedisClient.get_client()


@asynccontextmanager
async def redis_lock(
    key: str,
    timeout_seconds: int = 10,
    blocking: bool = True,
) -> AsyncGenerator[bool, None]:
    """
    Distributed lock using Redis.

    Usage:
        async with redis_lock("my-resource") as acquired:
            if acquired:
                # Do work with lock
                pass
    """
    import uuid

    client = RedisClient.get_client()
    lock_key = f"lock:{key}"
    lock_value = str(uuid.uuid4())

    try:
        # Try to acquire lock
        acquired = await client.set(
            lock_key,
            lock_value,
            nx=True,
            ex=timeout_seconds,
        )

        if not acquired and blocking:
            # Wait and retry
            import asyncio

            for _ in range(timeout_seconds * 10):
                await asyncio.sleep(0.1)
                acquired = await client.set(
                    lock_key,
                    lock_value,
                    nx=True,
                    ex=timeout_seconds,
                )
                if acquired:
                    break

        yield bool(acquired)

    finally:
        # Release lock only if we own it
        current = await client.get(lock_key)
        if current == lock_value:
            await client.delete(lock_key)

