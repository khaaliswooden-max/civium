"""
Regulatory Source Scrapers
==========================

Web scrapers for official regulatory sources.

Supported sources:
- US Federal Register (federalregister.gov)
- EU EUR-Lex (eur-lex.europa.eu)
- UK Legislation (legislation.gov.uk)
- More to come...

Version: 0.1.0
"""

from services.regulatory_intelligence.scrapers.base import (
    BaseScraper,
    ScrapedDocument,
    ScraperConfig,
)
from services.regulatory_intelligence.scrapers.federal_register import (
    FederalRegisterScraper,
)
from services.regulatory_intelligence.scrapers.eurlex import (
    EURLexScraper,
)

__all__ = [
    # Base
    "BaseScraper",
    "ScrapedDocument",
    "ScraperConfig",
    # Implementations
    "FederalRegisterScraper",
    "EURLexScraper",
]

