"""
Kafka Client
============

Async Kafka producer and consumer for event streaming.

Version: 0.1.0
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from shared.config import settings
from shared.logging import get_logger

logger = get_logger(__name__)


class KafkaClient:
    """
    Async Kafka client wrapper.

    Manages producer and consumer lifecycle.
    """

    _producer: AIOKafkaProducer | None = None

    @classmethod
    async def get_producer(cls) -> AIOKafkaProducer:
        """Get or create the async producer."""
        if cls._producer is None:
            cls._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka.bootstrap_servers,
                security_protocol=settings.kafka.security_protocol,
                value_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
                key_serializer=lambda k: k.encode("utf-8") if k and isinstance(k, str) else k,
                compression_type="gzip",
                acks="all",
                retries=3,
            )
            await cls._producer.start()
            logger.info(
                "kafka_producer_created",
                bootstrap_servers=settings.kafka.bootstrap_servers,
            )
        return cls._producer

    @classmethod
    async def create_consumer(
        cls,
        topics: list[str],
        group_id: str,
        auto_offset_reset: str = "latest",
    ) -> AIOKafkaConsumer:
        """
        Create a new consumer instance.

        Args:
            topics: List of topics to subscribe to
            group_id: Consumer group ID
            auto_offset_reset: Where to start reading ('earliest' or 'latest')

        Returns:
            AIOKafkaConsumer instance (not started)
        """
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=settings.kafka.bootstrap_servers,
            security_protocol=settings.kafka.security_protocol,
            group_id=group_id,
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=True,
            value_deserializer=lambda v: v.decode("utf-8"),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
        )
        return consumer

    @classmethod
    async def close(cls) -> None:
        """Close the producer."""
        if cls._producer is not None:
            await cls._producer.stop()
            cls._producer = None
            logger.info("kafka_producer_closed")

    @classmethod
    async def health_check(cls) -> dict[str, Any]:
        """
        Check Kafka health.

        Returns:
            dict with status and cluster info
        """
        import time

        try:
            start = time.perf_counter()
            producer = await cls.get_producer()

            # Get cluster metadata
            metadata = await producer.client.fetch_all_metadata()
            latency_ms = (time.perf_counter() - start) * 1000

            return {
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
                "brokers": len(metadata.brokers()),
                "topics": len(metadata.topics()),
            }
        except Exception as e:
            logger.error("kafka_health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    # =========================================================================
    # Publishing
    # =========================================================================

    @classmethod
    async def publish(
        cls,
        topic: str,
        value: str | bytes | dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Publish a message to a topic.

        Args:
            topic: Topic name
            value: Message value (str, bytes, or dict)
            key: Optional message key for partitioning
            headers: Optional message headers
        """
        import json

        producer = await cls.get_producer()

        # Serialize dict to JSON
        if isinstance(value, dict):
            value = json.dumps(value)

        # Convert headers to tuple format
        kafka_headers = None
        if headers:
            kafka_headers = [(k, v.encode("utf-8")) for k, v in headers.items()]

        await producer.send_and_wait(
            topic,
            value=value.encode("utf-8") if isinstance(value, str) else value,
            key=key,
            headers=kafka_headers,
        )

        logger.debug(
            "kafka_message_published",
            topic=topic,
            key=key,
        )

    @classmethod
    async def publish_batch(
        cls,
        topic: str,
        messages: list[dict[str, Any]],
    ) -> int:
        """
        Publish multiple messages to a topic.

        Args:
            topic: Topic name
            messages: List of message dicts with 'value' and optional 'key'

        Returns:
            Number of messages published
        """
        import json

        producer = await cls.get_producer()
        count = 0

        batch = producer.create_batch()
        for msg in messages:
            value = msg["value"]
            if isinstance(value, dict):
                value = json.dumps(value)
            if isinstance(value, str):
                value = value.encode("utf-8")

            key = msg.get("key")
            if key and isinstance(key, str):
                key = key.encode("utf-8")

            metadata = batch.append(key=key, value=value, timestamp=None)
            if metadata is None:
                # Batch is full, send it
                await producer.send_batch(batch, topic)
                batch = producer.create_batch()
                batch.append(key=key, value=value, timestamp=None)

            count += 1

        # Send remaining messages
        if batch.record_count() > 0:
            await producer.send_batch(batch, topic)

        logger.debug(
            "kafka_batch_published",
            topic=topic,
            count=count,
        )

        return count


# Predefined topics
class Topics:
    """Kafka topic names."""

    COMPLIANCE_EVENTS = "civium.compliance.events"
    REGULATORY_CHANGES = "civium.regulatory.changes"
    ENTITY_UPDATES = "civium.entity.updates"
    ASSESSMENT_RESULTS = "civium.assessment.results"
    AUDIT_LOGS = "civium.audit.logs"
    ALERTS = "civium.alerts"


async def get_kafka_producer() -> AIOKafkaProducer:
    """
    Dependency that provides the Kafka producer.

    Usage:
        @app.post("/events")
        async def events(producer: AIOKafkaProducer = Depends(get_kafka_producer)):
            await producer.send_and_wait("topic", b"message")
    """
    return await KafkaClient.get_producer()


async def get_kafka_consumer(
    topics: list[str],
    group_id: str,
) -> AIOKafkaConsumer:
    """
    Create a Kafka consumer for the given topics.

    Args:
        topics: Topics to subscribe to
        group_id: Consumer group ID

    Returns:
        Started consumer instance
    """
    consumer = await KafkaClient.create_consumer(topics, group_id)
    await consumer.start()
    return consumer


@asynccontextmanager
async def kafka_consumer_context(
    topics: list[str],
    group_id: str,
) -> AsyncGenerator[AIOKafkaConsumer, None]:
    """
    Context manager for Kafka consumer.

    Usage:
        async with kafka_consumer_context(["topic"], "group") as consumer:
            async for msg in consumer:
                process(msg)
    """
    consumer = await get_kafka_consumer(topics, group_id)
    try:
        yield consumer
    finally:
        await consumer.stop()


async def consume_messages(
    topics: list[str],
    group_id: str,
    handler: Callable[[Any], Any],
    max_messages: int | None = None,
) -> int:
    """
    Consume messages from topics and process with handler.

    Args:
        topics: Topics to consume from
        group_id: Consumer group ID
        handler: Async function to process each message
        max_messages: Maximum messages to process (None for infinite)

    Returns:
        Number of messages processed
    """
    count = 0
    async with kafka_consumer_context(topics, group_id) as consumer:
        async for msg in consumer:
            try:
                await handler(msg)
                count += 1

                if max_messages and count >= max_messages:
                    break

            except Exception as e:
                logger.error(
                    "kafka_message_processing_error",
                    topic=msg.topic,
                    offset=msg.offset,
                    error=str(e),
                )

    return count

