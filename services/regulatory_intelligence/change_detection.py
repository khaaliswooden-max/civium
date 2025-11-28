"""
Regulatory Change Detection System
===================================

Monitors regulatory sources for changes and triggers updates.

Features:
- Scheduled monitoring of regulatory sources
- Content hash comparison for change detection
- Diff generation for changed documents
- Notification system integration
- Event publishing to Kafka

Version: 0.1.0
"""

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import Any

from shared.database.kafka import KafkaClient, Topics
from shared.database.mongodb import MongoDBClient
from shared.database.redis import RedisClient
from shared.logging import get_logger
from services.regulatory_intelligence.scrapers.base import BaseScraper, DocumentType
from services.regulatory_intelligence.nlp.rml import RMLDocument, RMLGenerator

logger = get_logger(__name__)


class ChangeType(str, Enum):
    """Types of regulatory changes."""

    NEW = "new"
    MODIFIED = "modified"
    DELETED = "deleted"
    SUPERSEDED = "superseded"


class ChangeSeverity(str, Enum):
    """Severity levels for changes."""

    LOW = "low"  # Minor text changes, formatting
    MEDIUM = "medium"  # Substantive changes to existing requirements
    HIGH = "high"  # New requirements or significant modifications
    CRITICAL = "critical"  # Changes affecting enforcement, penalties


@dataclass
class DetectedChange:
    """A detected change in a regulation."""

    regulation_id: str
    requirement_id: str | None = None

    change_type: ChangeType = ChangeType.MODIFIED
    severity: ChangeSeverity = ChangeSeverity.MEDIUM

    # Change details
    summary: str = ""
    old_content: str | None = None
    new_content: str | None = None
    diff: dict[str, Any] = field(default_factory=dict)

    # Source info
    source: str = ""
    source_id: str = ""
    source_url: str | None = None

    # Timestamps
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    effective_at: datetime | None = None

    # Processing status
    notification_sent: bool = False
    processed: bool = False


@dataclass
class MonitoringJob:
    """A scheduled monitoring job."""

    id: str
    source: str  # Scraper source name
    jurisdiction: str

    # Schedule
    cron_expression: str = "0 6 * * *"  # Daily at 6 AM
    last_run: datetime | None = None
    next_run: datetime | None = None

    # Filters
    document_types: list[DocumentType] = field(default_factory=list)
    agencies: list[str] = field(default_factory=list)

    # Status
    enabled: bool = True
    run_count: int = 0
    last_error: str | None = None


class ChangeDetector:
    """
    Detects changes in regulatory documents.

    Compares current and previous versions using:
    - Content hashes for quick change detection
    - Text diffing for detailed changes
    - RML comparison for structural changes
    """

    def __init__(self) -> None:
        """Initialize change detector."""
        self.rml_generator = RMLGenerator()

    async def detect_changes(
        self,
        old_rml: RMLDocument | None,
        new_rml: RMLDocument,
    ) -> list[DetectedChange]:
        """
        Detect changes between two versions of a regulation.

        Args:
            old_rml: Previous RML version (None for new regulations)
            new_rml: Current RML version

        Returns:
            List of detected changes
        """
        changes: list[DetectedChange] = []

        # New regulation
        if old_rml is None:
            changes.append(
                DetectedChange(
                    regulation_id=new_rml.id,
                    change_type=ChangeType.NEW,
                    severity=ChangeSeverity.HIGH,
                    summary=f"New regulation: {new_rml.name}",
                    new_content=new_rml.to_json()[:1000],
                )
            )
            return changes

        # Quick hash comparison
        if old_rml.document_hash == new_rml.document_hash:
            return []  # No changes

        # Detailed comparison
        diff = self.rml_generator.diff(old_rml, new_rml)

        # Added requirements
        for added in diff.get("added_requirements", []):
            changes.append(
                DetectedChange(
                    regulation_id=new_rml.id,
                    requirement_id=added.get("id"),
                    change_type=ChangeType.NEW,
                    severity=ChangeSeverity.HIGH,
                    summary=f"New requirement: {added.get('article_ref', 'Unknown')}",
                    new_content=added.get("text", "")[:500],
                    diff=added,
                )
            )

        # Removed requirements
        for removed in diff.get("removed_requirements", []):
            changes.append(
                DetectedChange(
                    regulation_id=new_rml.id,
                    requirement_id=removed.get("id"),
                    change_type=ChangeType.DELETED,
                    severity=ChangeSeverity.MEDIUM,
                    summary=f"Removed requirement: {removed.get('article_ref', 'Unknown')}",
                    old_content=removed.get("text", "")[:500],
                    diff=removed,
                )
            )

        # Modified requirements
        for modified in diff.get("modified_requirements", []):
            changes.append(
                DetectedChange(
                    regulation_id=new_rml.id,
                    requirement_id=modified.get("id"),
                    change_type=ChangeType.MODIFIED,
                    severity=self._assess_severity(modified),
                    summary=f"Modified requirement: {modified.get('article_ref', 'Unknown')}",
                    old_content=modified.get("changes", {}).get("text", {}).get("old", "")[:500],
                    new_content=modified.get("changes", {}).get("text", {}).get("new", "")[:500],
                    diff=modified,
                )
            )

        # Metadata changes
        for field_name, field_change in diff.get("metadata_changes", {}).items():
            changes.append(
                DetectedChange(
                    regulation_id=new_rml.id,
                    change_type=ChangeType.MODIFIED,
                    severity=ChangeSeverity.LOW,
                    summary=f"Metadata change: {field_name}",
                    old_content=str(field_change.get("old")),
                    new_content=str(field_change.get("new")),
                )
            )

        return changes

    def _assess_severity(self, change: dict[str, Any]) -> ChangeSeverity:
        """Assess severity of a change."""
        text_changes = change.get("changes", {}).get("text", {})
        old_text = text_changes.get("old", "")
        new_text = text_changes.get("new", "")

        # Check for penalty-related changes
        penalty_keywords = ["penalty", "fine", "imprisonment", "sanction", "violation"]
        if any(kw in new_text.lower() for kw in penalty_keywords):
            return ChangeSeverity.CRITICAL

        # Check for significant word changes
        old_words = set(old_text.lower().split())
        new_words = set(new_text.lower().split())
        changed_words = len(old_words.symmetric_difference(new_words))
        total_words = max(len(old_words), len(new_words), 1)

        if changed_words / total_words > 0.5:
            return ChangeSeverity.HIGH
        elif changed_words / total_words > 0.2:
            return ChangeSeverity.MEDIUM
        else:
            return ChangeSeverity.LOW


class ChangeMonitor:
    """
    Monitors regulatory sources for changes.

    Runs scheduled jobs to check for updates and
    triggers processing of detected changes.
    """

    def __init__(
        self,
        scrapers: dict[str, BaseScraper] | None = None,
        check_interval_hours: int = 24,
    ) -> None:
        """
        Initialize the change monitor.

        Args:
            scrapers: Dictionary of source_name -> scraper
            check_interval_hours: Default check interval
        """
        self.scrapers = scrapers or {}
        self.check_interval_hours = check_interval_hours
        self.detector = ChangeDetector()

        self._running = False
        self._jobs: dict[str, MonitoringJob] = {}

    async def start(self) -> None:
        """Start the monitoring loop."""
        self._running = True
        logger.info("change_monitor_started")

        while self._running:
            try:
                await self._run_due_jobs()
            except Exception as e:
                logger.error("monitor_loop_error", error=str(e))

            await asyncio.sleep(60)  # Check every minute

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        logger.info("change_monitor_stopped")

    def add_job(self, job: MonitoringJob) -> None:
        """Add a monitoring job."""
        self._jobs[job.id] = job
        logger.info("monitoring_job_added", job_id=job.id, source=job.source)

    def remove_job(self, job_id: str) -> None:
        """Remove a monitoring job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            logger.info("monitoring_job_removed", job_id=job_id)

    async def _run_due_jobs(self) -> None:
        """Run any jobs that are due."""
        now = datetime.now(UTC)

        for job in self._jobs.values():
            if not job.enabled:
                continue

            if job.next_run and now < job.next_run:
                continue

            try:
                await self._execute_job(job)
                job.last_run = now
                job.next_run = now + timedelta(hours=self.check_interval_hours)
                job.run_count += 1
                job.last_error = None
            except Exception as e:
                job.last_error = str(e)
                logger.error(
                    "monitoring_job_failed",
                    job_id=job.id,
                    error=str(e),
                )

    async def _execute_job(self, job: MonitoringJob) -> None:
        """Execute a single monitoring job."""
        logger.info(
            "executing_monitoring_job",
            job_id=job.id,
            source=job.source,
        )

        scraper = self.scrapers.get(job.source)
        if not scraper:
            raise ValueError(f"No scraper for source: {job.source}")

        # Get recent documents from source
        changes_found = 0
        async for doc in scraper.get_recent_documents(
            days=max(1, self.check_interval_hours // 24 + 1),
            document_types=job.document_types or None,
        ):
            # Check for changes
            change = await self._check_document_for_changes(doc, job)
            if change:
                changes_found += 1

        logger.info(
            "monitoring_job_completed",
            job_id=job.id,
            documents_checked=changes_found,
        )

    async def _check_document_for_changes(
        self,
        doc: Any,  # ScrapedDocument
        job: MonitoringJob,
    ) -> DetectedChange | None:
        """Check a single document for changes."""
        db = MongoDBClient.get_database()

        # Get stored hash
        cache_key = f"doc_hash:{doc.source}:{doc.source_id}"
        stored_hash = await RedisClient.get_cached(cache_key)

        if stored_hash == doc.content_hash:
            return None  # No change

        # Document is new or changed
        change = DetectedChange(
            regulation_id=f"REG-{job.jurisdiction}-{doc.source_id}",
            change_type=ChangeType.NEW if stored_hash is None else ChangeType.MODIFIED,
            severity=ChangeSeverity.MEDIUM,
            summary=f"{'New' if stored_hash is None else 'Updated'}: {doc.title}",
            new_content=doc.content[:1000],
            source=doc.source,
            source_id=doc.source_id,
            source_url=doc.source_url,
        )

        # Store change in MongoDB
        await db.regulatory_changes.insert_one({
            "regulation_id": change.regulation_id,
            "change_type": change.change_type.value,
            "severity": change.severity.value,
            "summary": change.summary,
            "source": change.source,
            "source_id": change.source_id,
            "detected_at": change.detected_at,
            "notification_sent": False,
        })

        # Update hash in cache
        await RedisClient.set_cached(cache_key, doc.content_hash, ttl_seconds=86400 * 30)

        # Publish event to Kafka
        await self._publish_change_event(change)

        logger.info(
            "change_detected",
            regulation_id=change.regulation_id,
            change_type=change.change_type.value,
            severity=change.severity.value,
        )

        return change

    async def _publish_change_event(self, change: DetectedChange) -> None:
        """Publish change event to Kafka."""
        try:
            await KafkaClient.publish(
                topic=Topics.REGULATORY_CHANGES,
                value={
                    "event_type": "regulatory_change",
                    "regulation_id": change.regulation_id,
                    "change_type": change.change_type.value,
                    "severity": change.severity.value,
                    "summary": change.summary,
                    "detected_at": change.detected_at.isoformat(),
                },
                key=change.regulation_id,
            )
        except Exception as e:
            logger.error("kafka_publish_failed", error=str(e))


async def run_change_detection_service() -> None:
    """
    Run the change detection service.

    This should be run as a background service.
    """
    from services.regulatory_intelligence.scrapers import (
        FederalRegisterScraper,
        EURLexScraper,
    )

    # Initialize scrapers
    scrapers: dict[str, BaseScraper] = {
        "federal_register": FederalRegisterScraper(),
        "eurlex": EURLexScraper(),
    }

    # Initialize monitor
    monitor = ChangeMonitor(scrapers=scrapers, check_interval_hours=24)

    # Add default monitoring jobs
    monitor.add_job(
        MonitoringJob(
            id="us_federal_rules",
            source="federal_register",
            jurisdiction="US",
            document_types=[DocumentType.RULE, DocumentType.PROPOSED_RULE],
        )
    )

    monitor.add_job(
        MonitoringJob(
            id="eu_regulations",
            source="eurlex",
            jurisdiction="EU",
            document_types=[DocumentType.REGULATION, DocumentType.DIRECTIVE],
        )
    )

    # Start monitoring
    try:
        await monitor.start()
    except asyncio.CancelledError:
        await monitor.stop()
    finally:
        # Clean up scrapers
        for scraper in scrapers.values():
            await scraper.close()

