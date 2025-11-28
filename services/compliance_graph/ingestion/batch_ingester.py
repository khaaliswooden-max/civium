"""
Batch Graph Ingester
====================

Efficient batch ingestion of multiple RML documents into Neo4j.

Version: 0.1.0
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from shared.database.neo4j import Neo4jClient
from shared.logging import get_logger

from services.compliance_graph.ingestion.rml_ingester import (
    RMLIngester,
    IngestionOptions,
    IngestionResult,
)

logger = get_logger(__name__)


@dataclass
class BatchResult:
    """Result of batch ingestion."""

    # Counts
    documents_processed: int = 0
    documents_succeeded: int = 0
    documents_failed: int = 0

    # Aggregated counts
    total_regulations: int = 0
    total_requirements: int = 0
    total_relationships: int = 0

    # Per-document results
    results: list[dict[str, Any]] = field(default_factory=list)

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Percentage of documents successfully processed."""
        if self.documents_processed == 0:
            return 0.0
        return self.documents_succeeded / self.documents_processed


class BatchIngester:
    """
    Batch ingestion of RML documents into Neo4j.

    Features:
    - Parallel processing with concurrency control
    - Progress tracking
    - Transaction batching
    - Error isolation (one failure doesn't stop others)
    """

    def __init__(
        self,
        options: IngestionOptions | None = None,
        max_concurrent: int = 5,
    ) -> None:
        """
        Initialize the batch ingester.

        Args:
            options: Ingestion options
            max_concurrent: Maximum concurrent ingestions
        """
        self.options = options or IngestionOptions()
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def ingest_batch(
        self,
        documents: list[dict[str, Any]],
        on_progress: callable | None = None,
    ) -> BatchResult:
        """
        Ingest multiple RML documents.

        Args:
            documents: List of RML documents
            on_progress: Optional callback(current, total, doc_id)

        Returns:
            BatchResult with aggregated counts
        """
        result = BatchResult()
        total = len(documents)

        # Process documents with concurrency control
        tasks = []
        for i, doc in enumerate(documents):
            task = self._ingest_with_semaphore(
                doc,
                i + 1,
                total,
                on_progress,
            )
            tasks.append(task)

        # Wait for all tasks
        doc_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        for i, doc_result in enumerate(doc_results):
            result.documents_processed += 1
            doc_id = documents[i].get("id", f"doc_{i}")

            if isinstance(doc_result, Exception):
                result.documents_failed += 1
                result.results.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": str(doc_result),
                })
            elif isinstance(doc_result, IngestionResult):
                if doc_result.success:
                    result.documents_succeeded += 1
                else:
                    result.documents_failed += 1

                result.total_regulations += doc_result.regulations_created
                result.total_requirements += doc_result.requirements_created
                result.total_relationships += doc_result.relationships_created

                result.results.append({
                    "document_id": doc_id,
                    "success": doc_result.success,
                    "regulations_created": doc_result.regulations_created,
                    "requirements_created": doc_result.requirements_created,
                    "relationships_created": doc_result.relationships_created,
                    "errors": doc_result.errors,
                })

        result.completed_at = datetime.now(UTC)
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

        logger.info(
            "batch_ingestion_complete",
            documents=result.documents_processed,
            succeeded=result.documents_succeeded,
            failed=result.documents_failed,
            requirements=result.total_requirements,
            duration=f"{result.duration_seconds:.2f}s",
        )

        return result

    async def _ingest_with_semaphore(
        self,
        document: dict[str, Any],
        current: int,
        total: int,
        on_progress: callable | None,
    ) -> IngestionResult:
        """Ingest a single document with semaphore control."""
        async with self._semaphore:
            ingester = RMLIngester(self.options)
            result = await ingester.ingest(document)

            if on_progress:
                try:
                    on_progress(current, total, document.get("id", ""))
                except Exception:
                    pass  # Don't fail on callback errors

            return result

    async def ingest_from_mongodb(
        self,
        query: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> BatchResult:
        """
        Ingest RML documents from MongoDB.

        Args:
            query: MongoDB query filter
            limit: Maximum documents to process

        Returns:
            BatchResult
        """
        from shared.database.mongodb import MongoDBClient

        db = MongoDBClient.get_database()

        # Fetch documents
        cursor = db.regulations.find(query or {})
        if limit:
            cursor = cursor.limit(limit)

        documents = []
        async for doc in cursor:
            if doc.get("rml"):
                documents.append(doc["rml"])

        logger.info(
            "batch_ingestion_from_mongodb",
            documents_found=len(documents),
            query=query,
        )

        return await self.ingest_batch(documents)


async def sync_regulations_to_graph(
    regulation_ids: list[str] | None = None,
) -> BatchResult:
    """
    Sync regulations from MongoDB to Neo4j graph.

    Args:
        regulation_ids: Specific regulation IDs to sync (None = all)

    Returns:
        BatchResult
    """
    from shared.database.mongodb import MongoDBClient

    db = MongoDBClient.get_database()

    # Build query
    query: dict[str, Any] = {"rml": {"$exists": True}}
    if regulation_ids:
        query["_id"] = {"$in": regulation_ids}

    # Fetch and ingest
    ingester = BatchIngester()
    return await ingester.ingest_from_mongodb(query)


async def clear_graph() -> dict[str, int]:
    """
    Clear all nodes and relationships from the graph.

    WARNING: Destructive operation!

    Returns:
        Counts of deleted nodes and relationships
    """
    # Delete all relationships first
    rel_result = await Neo4jClient.run_write_query(
        "MATCH ()-[r]->() DELETE r RETURN count(r) as count"
    )

    # Delete all nodes
    node_result = await Neo4jClient.run_write_query(
        "MATCH (n) DELETE n RETURN count(n) as count"
    )

    logger.warning(
        "graph_cleared",
        relationships_deleted=rel_result.get("relationships_deleted", 0),
        nodes_deleted=node_result.get("nodes_deleted", 0),
    )

    return {
        "relationships_deleted": rel_result.get("relationships_deleted", 0),
        "nodes_deleted": node_result.get("nodes_deleted", 0),
    }

