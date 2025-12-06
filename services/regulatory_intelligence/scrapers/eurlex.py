"""
EUR-Lex Scraper
===============

Scraper for the EU Official Journal and EUR-Lex (eur-lex.europa.eu).

EUR-Lex provides access to:
- EU Regulations (directly applicable)
- EU Directives (require national implementation)
- EU Decisions
- Treaties
- Case law

API Documentation: https://eur-lex.europa.eu/content/help/eurlex-content/web-services.html

Version: 0.1.0
"""

import re
from collections.abc import AsyncGenerator
from datetime import date, timedelta
from typing import Any

from services.regulatory_intelligence.scrapers.base import (
    BaseScraper,
    DocumentType,
    ScrapedDocument,
    SearchResult,
)
from shared.logging import get_logger


logger = get_logger(__name__)


# Map EUR-Lex document types to our types
EURLEX_TYPE_MAP = {
    "REG": DocumentType.REGULATION,
    "DIR": DocumentType.DIRECTIVE,
    "DEC": DocumentType.REGULATION,
    "TREATY": DocumentType.REGULATION,
    "RECOMMENDATION": DocumentType.GUIDANCE,
    "OPINION": DocumentType.NOTICE,
}


class EURLexScraper(BaseScraper):
    """
    Scraper for EUR-Lex (EU Official Journal).

    Uses the EUR-Lex SPARQL endpoint and REST API for access
    to EU legal documents.
    """

    API_BASE = "https://eur-lex.europa.eu"
    SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

    @property
    def source_name(self) -> str:
        return "eurlex"

    @property
    def base_url(self) -> str:
        return "https://eur-lex.europa.eu"

    @property
    def jurisdiction(self) -> str:
        return "EU"

    async def search(
        self,
        query: str,
        start_date: date | None = None,
        end_date: date | None = None,
        document_types: list[DocumentType] | None = None,
        limit: int = 100,
    ) -> list[SearchResult]:
        """
        Search EUR-Lex for documents.

        Args:
            query: Search query
            start_date: Start of date range
            end_date: End of date range
            document_types: Filter by document types
            limit: Maximum results
        """
        # Build search URL with query parameters
        params: dict[str, Any] = {
            "text": query,
            "sortOrder": "DATE_DESC",
            "page": 1,
            "pageSize": min(limit, 100),
        }

        if start_date:
            params["datePubFrom"] = start_date.strftime("%d/%m/%Y")

        if end_date:
            params["datePubTo"] = end_date.strftime("%d/%m/%Y")

        # Filter by document type
        if document_types:
            type_codes = []
            for dt in document_types:
                if dt == DocumentType.REGULATION:
                    type_codes.append("REG")
                elif dt == DocumentType.DIRECTIVE:
                    type_codes.append("DIR")
            if type_codes:
                params["type"] = ",".join(type_codes)

        try:
            response = await self._request(
                "GET",
                f"{self.API_BASE}/search.html",
                params=params,
            )

            # Parse HTML response to extract results
            results = self._parse_search_results(response.text)

            logger.info(
                "eurlex_search",
                query=query,
                results=len(results),
            )

            return results[:limit]

        except Exception as e:
            logger.error("eurlex_search_failed", error=str(e))
            # Fallback to SPARQL search
            return await self._sparql_search(query, start_date, end_date, limit)

    async def _sparql_search(
        self,
        query: str,
        start_date: date | None,
        end_date: date | None,
        limit: int,
    ) -> list[SearchResult]:
        """
        Search using SPARQL endpoint as fallback.
        """
        # Build SPARQL query
        date_filter = ""
        if start_date:
            date_filter += f'FILTER(?date >= "{start_date.isoformat()}"^^xsd:date)'
        if end_date:
            date_filter += f'FILTER(?date <= "{end_date.isoformat()}"^^xsd:date)'

        sparql_query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        
        SELECT DISTINCT ?celex ?title ?date ?type WHERE {{
            ?work cdm:work_has_expression ?expr .
            ?work cdm:resource_legal_id_celex ?celex .
            ?work cdm:work_date_document ?date .
            ?work cdm:resource_legal_type ?type .
            ?expr cdm:expression_title ?title .
            FILTER(LANG(?title) = "en" || LANG(?title) = "")
            FILTER(CONTAINS(LCASE(?title), LCASE("{query}")))
            {date_filter}
        }}
        ORDER BY DESC(?date)
        LIMIT {limit}
        """

        try:
            response = await self._request(
                "POST",
                self.SPARQL_ENDPOINT,
                data={"query": sparql_query},
                headers={"Accept": "application/sparql-results+json"},
            )

            data = response.json()
            results: list[SearchResult] = []

            for binding in data.get("results", {}).get("bindings", []):
                celex = binding.get("celex", {}).get("value", "")
                title = binding.get("title", {}).get("value", "")
                date_str = binding.get("date", {}).get("value", "")
                doc_type = binding.get("type", {}).get("value", "")

                pub_date = None
                if date_str:
                    try:
                        pub_date = date.fromisoformat(date_str[:10])
                    except ValueError:
                        pass

                # Determine document type from CELEX
                detected_type = DocumentType.REGULATION
                if "DIR" in doc_type or (celex.startswith("3") and "L" in celex):
                    detected_type = DocumentType.DIRECTIVE
                elif "DEC" in doc_type:
                    detected_type = DocumentType.REGULATION

                results.append(
                    SearchResult(
                        source_id=celex,
                        title=title,
                        publication_date=pub_date,
                        document_type=detected_type,
                        url=f"{self.base_url}/legal-content/EN/TXT/?uri=CELEX:{celex}",
                    )
                )

            return results

        except Exception as e:
            logger.error("sparql_search_failed", error=str(e))
            return []

    async def get_document(self, source_id: str) -> ScrapedDocument:
        """
        Get a EUR-Lex document by CELEX number.

        Args:
            source_id: CELEX identifier (e.g., "32016R0679" for GDPR)
        """
        # Get document in HTML format
        doc_url = f"{self.API_BASE}/legal-content/EN/TXT/HTML/?uri=CELEX:{source_id}"

        response = await self._request("GET", doc_url)
        html_content = response.text

        # Parse document metadata from HTML
        title = self._extract_title(html_content)
        pub_date = self._extract_date(html_content)
        doc_type = self._detect_document_type(source_id)

        # Clean content
        text_content = self._clean_html_content(html_content)

        # Extract ELI (European Legislation Identifier) if present
        eli = self._extract_eli(html_content)

        doc = ScrapedDocument(
            source=self.source_name,
            source_id=source_id,
            source_url=doc_url,
            title=title or f"EUR-Lex Document {source_id}",
            content=text_content,
            content_html=html_content,
            document_type=doc_type,
            jurisdiction=self.jurisdiction,
            jurisdictions=[self.jurisdiction],
            publication_date=pub_date,
            metadata={
                "celex": source_id,
                "eli": eli,
                "pdf_url": f"{self.API_BASE}/legal-content/EN/TXT/PDF/?uri=CELEX:{source_id}",
            },
        )

        logger.info(
            "eurlex_document_fetched",
            celex=source_id,
            title=doc.title[:100] if doc.title else "",
            chars=len(doc.content),
        )

        return doc

    async def get_recent_documents(
        self,
        days: int = 7,
        document_types: list[DocumentType] | None = None,
    ) -> AsyncGenerator[ScrapedDocument, None]:
        """
        Get recently published EUR-Lex documents.

        Args:
            days: Number of days to look back
            document_types: Filter by document types
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Default to regulations and directives
        if document_types is None:
            document_types = [DocumentType.REGULATION, DocumentType.DIRECTIVE]

        results = await self.search(
            query="",
            start_date=start_date,
            end_date=end_date,
            document_types=document_types,
            limit=200,
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

    async def get_regulation(self, year: int, number: int) -> ScrapedDocument:
        """
        Get an EU regulation by year and number.

        Args:
            year: Publication year
            number: Regulation number

        Example:
            get_regulation(2016, 679)  # GDPR
        """
        # CELEX format for regulations: 3YYYYR####
        celex = f"3{year}R{number:04d}"
        return await self.get_document(celex)

    async def get_directive(self, year: int, number: int) -> ScrapedDocument:
        """
        Get an EU directive by year and number.

        Args:
            year: Publication year
            number: Directive number
        """
        # CELEX format for directives: 3YYYYL####
        celex = f"3{year}L{number:04d}"
        return await self.get_document(celex)

    def _parse_search_results(self, html: str) -> list[SearchResult]:
        """Parse search results from HTML."""
        results: list[SearchResult] = []

        # Simple regex-based extraction
        # Look for CELEX numbers and titles
        pattern = r'CELEX[:\s]*(\d{5}[A-Z]\d{4})[^"]*"[^>]*>([^<]+)'
        matches = re.findall(pattern, html)

        for celex, title in matches:
            results.append(
                SearchResult(
                    source_id=celex,
                    title=title.strip(),
                    publication_date=None,
                    document_type=self._detect_document_type(celex),
                    url=f"{self.base_url}/legal-content/EN/TXT/?uri=CELEX:{celex}",
                )
            )

        return results

    def _detect_document_type(self, celex: str) -> DocumentType:
        """Detect document type from CELEX number."""
        if len(celex) >= 6:
            type_char = celex[5]
            if type_char == "R":
                return DocumentType.REGULATION
            elif type_char == "L":
                return DocumentType.DIRECTIVE
            elif type_char == "D":
                return DocumentType.REGULATION  # Decision

        return DocumentType.REGULATION

    def _extract_title(self, html: str) -> str | None:
        """Extract document title from HTML."""
        # Try meta title
        match = re.search(r"<title>([^<]+)</title>", html, re.I)
        if match:
            title = match.group(1).strip()
            # Clean up common prefixes
            title = re.sub(r"^EUR-Lex\s*[-–]\s*", "", title)
            return title

        # Try h1
        match = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
        if match:
            return match.group(1).strip()

        return None

    def _extract_date(self, html: str) -> date | None:
        """Extract publication date from HTML."""
        # Look for date patterns
        patterns = [
            r"(\d{1,2})[./](\d{1,2})[./](\d{4})",  # DD/MM/YYYY
            r"(\d{4})-(\d{2})-(\d{2})",  # YYYY-MM-DD
            r"(\d{1,2})\s+(\w+)\s+(\d{4})",  # DD Month YYYY
        ]

        for pattern in patterns:
            match = re.search(pattern, html[:5000])
            if match:
                try:
                    groups = match.groups()
                    if len(groups[0]) == 4:  # YYYY-MM-DD
                        return date(int(groups[0]), int(groups[1]), int(groups[2]))
                    elif len(groups[2]) == 4:  # DD/MM/YYYY
                        return date(int(groups[2]), int(groups[1]), int(groups[0]))
                except (ValueError, IndexError):
                    continue

        return None

    def _extract_eli(self, html: str) -> str | None:
        """Extract European Legislation Identifier (ELI)."""
        match = re.search(r'eli/[^"\'>\s]+', html)
        if match:
            return match.group(0)
        return None

    def _clean_html_content(self, html: str) -> str:
        """Clean HTML content to plain text."""
        if not html:
            return ""

        # Remove script and style elements
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)

        # Remove navigation and footer
        text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL | re.I)

        # Convert elements to text
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
