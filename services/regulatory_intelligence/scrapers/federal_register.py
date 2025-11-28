"""
Federal Register Scraper
========================

Scraper for the US Federal Register (federalregister.gov).

The Federal Register API provides access to:
- Final Rules
- Proposed Rules
- Notices
- Presidential Documents
- Executive Orders

API Documentation: https://www.federalregister.gov/developers/documentation/api/v1

Version: 0.1.0
"""

from collections.abc import AsyncGenerator
from datetime import date, timedelta
from typing import Any

from shared.logging import get_logger
from services.regulatory_intelligence.scrapers.base import (
    BaseScraper,
    DocumentType,
    ScrapedDocument,
    ScraperConfig,
    SearchResult,
)

logger = get_logger(__name__)


# Map Federal Register document types to our types
FR_TYPE_MAP = {
    "RULE": DocumentType.RULE,
    "PRORULE": DocumentType.PROPOSED_RULE,
    "NOTICE": DocumentType.NOTICE,
    "PRESDOCU": DocumentType.EXECUTIVE_ORDER,
}


class FederalRegisterScraper(BaseScraper):
    """
    Scraper for the US Federal Register.

    Uses the official Federal Register API for reliable access
    to regulatory documents.
    """

    API_BASE = "https://www.federalregister.gov/api/v1"

    @property
    def source_name(self) -> str:
        return "federal_register"

    @property
    def base_url(self) -> str:
        return "https://www.federalregister.gov"

    @property
    def jurisdiction(self) -> str:
        return "US"

    async def search(
        self,
        query: str,
        start_date: date | None = None,
        end_date: date | None = None,
        document_types: list[DocumentType] | None = None,
        limit: int = 100,
    ) -> list[SearchResult]:
        """
        Search the Federal Register.

        Args:
            query: Search query (supports full-text search)
            start_date: Start of publication date range
            end_date: End of publication date range
            document_types: Filter by document types
            limit: Maximum results (max 1000)
        """
        params: dict[str, Any] = {
            "per_page": min(limit, 1000),
            "order": "newest",
        }

        if query:
            params["conditions[term]"] = query

        if start_date:
            params["conditions[publication_date][gte]"] = start_date.isoformat()

        if end_date:
            params["conditions[publication_date][lte]"] = end_date.isoformat()

        if document_types:
            # Map our types to FR types
            fr_types = []
            for dt in document_types:
                for fr_type, our_type in FR_TYPE_MAP.items():
                    if our_type == dt:
                        fr_types.append(fr_type)
            if fr_types:
                params["conditions[type][]"] = fr_types

        response = await self._request(
            "GET",
            f"{self.API_BASE}/documents",
            params=params,
        )

        data = response.json()
        results: list[SearchResult] = []

        for item in data.get("results", []):
            pub_date = None
            if item.get("publication_date"):
                pub_date = date.fromisoformat(item["publication_date"])

            doc_type = FR_TYPE_MAP.get(
                item.get("type", ""),
                DocumentType.REGULATION,
            )

            results.append(
                SearchResult(
                    source_id=item.get("document_number", ""),
                    title=item.get("title", ""),
                    publication_date=pub_date,
                    document_type=doc_type,
                    url=item.get("html_url", ""),
                    snippet=item.get("abstract", "")[:500] if item.get("abstract") else None,
                    agencies=[
                        a.get("name", "")
                        for a in item.get("agencies", [])
                        if a.get("name")
                    ],
                )
            )

        logger.info(
            "federal_register_search",
            query=query,
            results=len(results),
        )

        return results

    async def get_document(self, source_id: str) -> ScrapedDocument:
        """
        Get a Federal Register document by document number.

        Args:
            source_id: Federal Register document number
        """
        # Get document metadata
        response = await self._request(
            "GET",
            f"{self.API_BASE}/documents/{source_id}",
        )

        data = response.json()

        # Get full text content
        full_text = ""
        if data.get("body_html_url"):
            try:
                text_response = await self._request(
                    "GET",
                    data["body_html_url"],
                )
                full_text = text_response.text
            except Exception as e:
                logger.warning(
                    "full_text_fetch_failed",
                    document_number=source_id,
                    error=str(e),
                )
                # Fall back to raw text URL
                if data.get("raw_text_url"):
                    text_response = await self._request(
                        "GET",
                        data["raw_text_url"],
                    )
                    full_text = text_response.text

        # Parse dates
        pub_date = None
        if data.get("publication_date"):
            pub_date = date.fromisoformat(data["publication_date"])

        effective_date = None
        if data.get("effective_on"):
            try:
                effective_date = date.fromisoformat(data["effective_on"])
            except ValueError:
                pass

        comment_end = None
        if data.get("comments_close_on"):
            try:
                comment_end = date.fromisoformat(data["comments_close_on"])
            except ValueError:
                pass

        # Get CFR references
        cfr_refs = []
        for cfr in data.get("cfr_references", []):
            title = cfr.get("title", "")
            parts = cfr.get("parts", [])
            for part in parts:
                cfr_refs.append(f"{title} CFR {part}")

        doc = ScrapedDocument(
            source=self.source_name,
            source_id=source_id,
            source_url=data.get("html_url", f"{self.base_url}/d/{source_id}"),
            title=data.get("title", ""),
            content=self._clean_html_content(full_text),
            content_html=full_text,
            document_type=FR_TYPE_MAP.get(
                data.get("type", ""),
                DocumentType.REGULATION,
            ),
            jurisdiction=self.jurisdiction,
            jurisdictions=[self.jurisdiction],
            publication_date=pub_date,
            effective_date=effective_date,
            comment_end_date=comment_end,
            agency=data.get("agencies", [{}])[0].get("name") if data.get("agencies") else None,
            agencies=[
                a.get("name", "")
                for a in data.get("agencies", [])
                if a.get("name")
            ],
            docket_ids=data.get("docket_ids", []),
            citation=data.get("citation"),
            cfr_references=cfr_refs,
            metadata={
                "abstract": data.get("abstract"),
                "action": data.get("action"),
                "dates": data.get("dates"),
                "regulation_id_numbers": data.get("regulation_id_numbers", []),
                "significant": data.get("significant"),
                "page_length": data.get("page_length"),
                "start_page": data.get("start_page"),
                "end_page": data.get("end_page"),
                "pdf_url": data.get("pdf_url"),
            },
        )

        logger.info(
            "federal_register_document_fetched",
            document_number=source_id,
            title=doc.title[:100],
            chars=len(doc.content),
        )

        return doc

    async def get_recent_documents(
        self,
        days: int = 7,
        document_types: list[DocumentType] | None = None,
    ) -> AsyncGenerator[ScrapedDocument, None]:
        """
        Get recently published Federal Register documents.

        Args:
            days: Number of days to look back
            document_types: Filter by document types
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Default to final rules and proposed rules
        if document_types is None:
            document_types = [DocumentType.RULE, DocumentType.PROPOSED_RULE]

        results = await self.search(
            query="",
            start_date=start_date,
            end_date=end_date,
            document_types=document_types,
            limit=500,
        )

        for result in results:
            try:
                doc = await self.get_document(result.source_id)
                yield doc
            except Exception as e:
                logger.error(
                    "document_fetch_failed",
                    source_id=result.source_id,
                    error=str(e),
                )

    async def get_by_agency(
        self,
        agency_slug: str,
        days: int = 30,
        limit: int = 100,
    ) -> list[SearchResult]:
        """
        Get documents from a specific agency.

        Args:
            agency_slug: Agency slug (e.g., "securities-and-exchange-commission")
            days: Days to look back
            limit: Maximum results
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        params = {
            "per_page": min(limit, 1000),
            "order": "newest",
            "conditions[agencies][]": agency_slug,
            "conditions[publication_date][gte]": start_date.isoformat(),
            "conditions[publication_date][lte]": end_date.isoformat(),
        }

        response = await self._request(
            "GET",
            f"{self.API_BASE}/documents",
            params=params,
        )

        data = response.json()
        results: list[SearchResult] = []

        for item in data.get("results", []):
            pub_date = None
            if item.get("publication_date"):
                pub_date = date.fromisoformat(item["publication_date"])

            results.append(
                SearchResult(
                    source_id=item.get("document_number", ""),
                    title=item.get("title", ""),
                    publication_date=pub_date,
                    document_type=FR_TYPE_MAP.get(
                        item.get("type", ""),
                        DocumentType.REGULATION,
                    ),
                    url=item.get("html_url", ""),
                    snippet=item.get("abstract", "")[:500] if item.get("abstract") else None,
                    agencies=[agency_slug],
                )
            )

        return results

    async def get_agencies(self) -> list[dict[str, Any]]:
        """
        Get list of all agencies.

        Returns:
            List of agency info dicts with id, name, slug, etc.
        """
        response = await self._request(
            "GET",
            f"{self.API_BASE}/agencies",
        )

        return response.json()

    def _clean_html_content(self, html: str) -> str:
        """
        Clean HTML content to plain text.

        Args:
            html: HTML content

        Returns:
            Cleaned plain text
        """
        import re

        if not html:
            return ""

        # Remove script and style elements
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)

        # Convert common elements to text equivalents
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"<p[^>]*>", "\n\n", text, flags=re.I)
        text = re.sub(r"</p>", "", text, flags=re.I)
        text = re.sub(r"<h\d[^>]*>", "\n\n", text, flags=re.I)
        text = re.sub(r"</h\d>", "\n", text, flags=re.I)
        text = re.sub(r"<li[^>]*>", "\n• ", text, flags=re.I)

        # Remove remaining tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        import html

        text = html.unescape(text)

        # Normalize whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

