"""
Base Scraper Module
===================

Abstract base class and common utilities for regulatory scrapers.

Version: 0.1.0
"""

import hashlib
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

import httpx

from shared.logging import get_logger


logger = get_logger(__name__)


class DocumentType(str, Enum):
    """Types of regulatory documents."""

    REGULATION = "regulation"
    DIRECTIVE = "directive"
    RULE = "rule"
    NOTICE = "notice"
    PROPOSED_RULE = "proposed_rule"
    EXECUTIVE_ORDER = "executive_order"
    GUIDANCE = "guidance"
    AMENDMENT = "amendment"


@dataclass
class ScraperConfig:
    """Configuration for scrapers."""

    # Rate limiting
    requests_per_minute: int = 30
    retry_count: int = 3
    retry_delay_seconds: float = 2.0

    # Timeouts
    connect_timeout: float = 10.0
    read_timeout: float = 60.0

    # User agent
    user_agent: str = "CiviumBot/1.0 (Regulatory Intelligence; compliance@civium.io)"

    # Proxy settings (optional)
    proxy_url: str | None = None

    # Cache settings
    cache_enabled: bool = True
    cache_ttl_hours: int = 24


@dataclass
class ScrapedDocument:
    """A document retrieved from a regulatory source."""

    # Source identification
    source: str  # e.g., "federal_register", "eurlex"
    source_id: str  # Original ID from source
    source_url: str

    # Content
    title: str
    content: str
    content_html: str | None = None

    # Classification
    document_type: DocumentType = DocumentType.REGULATION
    jurisdiction: str = ""
    jurisdictions: list[str] = field(default_factory=list)

    # Dates
    publication_date: date | None = None
    effective_date: date | None = None
    comment_end_date: date | None = None

    # Metadata from source
    agency: str | None = None
    agencies: list[str] = field(default_factory=list)
    docket_ids: list[str] = field(default_factory=list)
    citation: str | None = None
    cfr_references: list[str] = field(default_factory=list)

    # Document identification
    content_hash: str = ""

    # Scraping metadata
    scraped_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    scraper_version: str = "0.1.0"

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Compute derived fields."""
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()


@dataclass
class SearchResult:
    """A search result from a regulatory source."""

    source_id: str
    title: str
    publication_date: date | None
    document_type: DocumentType
    url: str
    snippet: str | None = None
    agencies: list[str] = field(default_factory=list)


class BaseScraper(ABC):
    """
    Abstract base class for regulatory scrapers.

    Provides common functionality:
    - Rate limiting
    - Retry logic
    - Caching
    - Error handling
    """

    def __init__(self, config: ScraperConfig | None = None) -> None:
        """
        Initialize the scraper.

        Args:
            config: Scraper configuration
        """
        self.config = config or ScraperConfig()
        self._client: httpx.AsyncClient | None = None
        self._request_count = 0
        self._last_request_time: datetime | None = None

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the regulatory source."""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL of the regulatory source."""
        ...

    @property
    @abstractmethod
    def jurisdiction(self) -> str:
        """Primary jurisdiction code."""
        ...

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            timeout = httpx.Timeout(
                connect=self.config.connect_timeout,
                read=self.config.read_timeout,
                write=30.0,
                pool=30.0,
            )

            self._client = httpx.AsyncClient(
                timeout=timeout,
                headers={
                    "User-Agent": self.config.user_agent,
                    "Accept": "application/json, text/html, application/pdf",
                },
                follow_redirects=True,
                http2=True,
            )

        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make an HTTP request with rate limiting and retry.

        Args:
            method: HTTP method
            url: URL to request
            **kwargs: Additional arguments for httpx

        Returns:
            HTTP response
        """
        import asyncio

        client = await self._get_client()

        # Rate limiting
        if self._last_request_time:
            elapsed = (datetime.now(UTC) - self._last_request_time).total_seconds()
            min_interval = 60.0 / self.config.requests_per_minute
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)

        # Retry logic
        last_error: Exception | None = None
        for attempt in range(self.config.retry_count):
            try:
                self._last_request_time = datetime.now(UTC)
                self._request_count += 1

                response = await client.request(method, url, **kwargs)
                response.raise_for_status()

                logger.debug(
                    "scraper_request",
                    source=self.source_name,
                    url=url,
                    status=response.status_code,
                )

                return response

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:  # Rate limited
                    wait_time = self.config.retry_delay_seconds * (attempt + 1) * 2
                    logger.warning(
                        "rate_limited",
                        source=self.source_name,
                        wait=wait_time,
                    )
                    await asyncio.sleep(wait_time)
                elif e.response.status_code >= 500:
                    await asyncio.sleep(self.config.retry_delay_seconds * (attempt + 1))
                else:
                    raise

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(
                    "request_failed",
                    source=self.source_name,
                    attempt=attempt + 1,
                    error=str(e),
                )
                await asyncio.sleep(self.config.retry_delay_seconds * (attempt + 1))

        raise last_error or RuntimeError(f"Request failed after {self.config.retry_count} attempts")

    @abstractmethod
    async def search(
        self,
        query: str,
        start_date: date | None = None,
        end_date: date | None = None,
        document_types: list[DocumentType] | None = None,
        limit: int = 100,
    ) -> list[SearchResult]:
        """
        Search for documents.

        Args:
            query: Search query
            start_date: Start of date range
            end_date: End of date range
            document_types: Filter by document types
            limit: Maximum results

        Returns:
            List of search results
        """
        ...

    @abstractmethod
    async def get_document(self, source_id: str) -> ScrapedDocument:
        """
        Get a specific document by ID.

        Args:
            source_id: Document ID from the source

        Returns:
            Scraped document
        """
        ...

    @abstractmethod
    async def get_recent_documents(
        self,
        days: int = 7,
        document_types: list[DocumentType] | None = None,
    ) -> AsyncGenerator[ScrapedDocument, None]:
        """
        Get recently published documents.

        Args:
            days: Number of days to look back
            document_types: Filter by document types

        Yields:
            Scraped documents
        """
        ...

    async def check_for_updates(
        self,
        source_id: str,
        known_hash: str,
    ) -> tuple[bool, str | None]:
        """
        Check if a document has been updated.

        Args:
            source_id: Document ID
            known_hash: Previously known content hash

        Returns:
            Tuple of (has_changed, new_hash)
        """
        try:
            doc = await self.get_document(source_id)
            has_changed = doc.content_hash != known_hash
            return has_changed, doc.content_hash
        except Exception as e:
            logger.error(
                "update_check_failed",
                source_id=source_id,
                error=str(e),
            )
            return False, None
