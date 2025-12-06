"""
Text Preprocessing Module
=========================

Cleans and normalizes regulatory text for NLP processing.

Features:
- Unicode normalization
- Legal citation extraction
- Section/article detection
- Reference normalization
- Noise removal

Version: 0.1.0
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from shared.logging import get_logger


logger = get_logger(__name__)


@dataclass
class Citation:
    """Legal citation reference."""

    raw_text: str
    citation_type: str  # statute, regulation, case, treaty
    identifier: str
    section: str | None = None
    title: str | None = None


@dataclass
class Section:
    """Detected document section."""

    number: str
    title: str | None
    content: str
    start_pos: int
    end_pos: int
    level: int = 1  # Hierarchy level (1 = chapter, 2 = section, etc.)


@dataclass
class PreprocessedDocument:
    """Result of document preprocessing."""

    # Cleaned content
    cleaned_text: str
    original_text: str

    # Extracted structure
    sections: list[Section] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)

    # Detected metadata
    effective_date: date | None = None
    jurisdiction: str | None = None
    regulation_type: str | None = None

    # Statistics
    sentence_count: int = 0
    word_count: int = 0

    # Processing metadata
    preprocessing_notes: list[str] = field(default_factory=list)


class TextPreprocessor:
    """
    Preprocesses regulatory text for NLP pipeline.

    Handles:
    - Text cleaning and normalization
    - Legal citation extraction
    - Section structure detection
    - Metadata extraction
    """

    # Common legal citation patterns
    CITATION_PATTERNS = {
        # US Code: 42 U.S.C. § 1234 or 42 USC 1234
        "us_code": re.compile(
            r"(\d+)\s*U\.?S\.?C\.?\s*[§]?\s*(\d+[a-z]?(?:-\d+)?(?:\([a-z0-9]+\))*)",
            re.IGNORECASE,
        ),
        # Code of Federal Regulations: 45 CFR 164.502
        "cfr": re.compile(
            r"(\d+)\s*C\.?F\.?R\.?\s*[§]?\s*(\d+(?:\.\d+)?(?:\([a-z0-9]+\))*)",
            re.IGNORECASE,
        ),
        # EU regulations: Regulation (EU) 2016/679
        "eu_regulation": re.compile(
            r"Regulation\s*\((?:EU|EC)\)\s*(?:No\.?\s*)?(\d+/\d+)",
            re.IGNORECASE,
        ),
        # EU directives: Directive 2014/65/EU
        "eu_directive": re.compile(
            r"Directive\s*(\d+/\d+/(?:EU|EC))",
            re.IGNORECASE,
        ),
        # UK statutory instruments: SI 2019/1234
        "uk_si": re.compile(
            r"S\.?I\.?\s*(\d+/\d+)",
            re.IGNORECASE,
        ),
        # General section references: Section 1.2.3 or § 1.2.3
        "section": re.compile(
            r"(?:Section|§|Art(?:icle)?\.?)\s*(\d+(?:[.\-]\d+)*(?:\([a-z0-9]+\))*)",
            re.IGNORECASE,
        ),
    }

    # Section header patterns
    SECTION_PATTERNS = [
        # Chapter/Article/Section with number and optional title
        re.compile(
            r"^(?P<type>CHAPTER|ARTICLE|SECTION|PART|TITLE|SUBPART|DIVISION)\s+"
            r"(?P<number>\d+(?:[.\-]\d+)*(?:\s*[A-Z])?)"
            r"(?:\s*[:\-—–]\s*|\s+)?"
            r"(?P<title>[A-Z][^\n]{0,200})?$",
            re.IGNORECASE | re.MULTILINE,
        ),
        # Numbered sections: 1.2.3 Title
        re.compile(
            r"^(?P<number>\d+(?:\.\d+)+)\s+"
            r"(?P<title>[A-Z][^\n]{0,200})$",
            re.MULTILINE,
        ),
        # Lettered sections: (a) Content
        re.compile(
            r"^\((?P<number>[a-z]|\d+)\)\s+"
            r"(?P<title>[A-Z][^\n]{0,200})$",
            re.MULTILINE,
        ),
    ]

    # Date patterns for effective date detection
    DATE_PATTERNS = [
        # "effective January 1, 2024" or "takes effect on January 1, 2024"
        re.compile(
            r"(?:effective|takes?\s+effect|in\s+force)\s+(?:on\s+)?(\w+\s+\d{1,2},?\s+\d{4})",
            re.IGNORECASE,
        ),
        # ISO date: 2024-01-15
        re.compile(r"(\d{4}-\d{2}-\d{2})"),
        # European format: 25 May 2018
        re.compile(r"(\d{1,2}\s+\w+\s+\d{4})"),
    ]

    def __init__(
        self,
        normalize_unicode: bool = True,
        extract_citations: bool = True,
        detect_sections: bool = True,
        remove_headers_footers: bool = True,
    ) -> None:
        """
        Initialize preprocessor with options.

        Args:
            normalize_unicode: Normalize Unicode characters
            extract_citations: Extract legal citations
            detect_sections: Detect document sections
            remove_headers_footers: Remove repeated headers/footers
        """
        self.normalize_unicode = normalize_unicode
        self.extract_citations = extract_citations
        self.detect_sections = detect_sections
        self.remove_headers_footers = remove_headers_footers

    def preprocess(self, text: str) -> PreprocessedDocument:
        """
        Preprocess regulatory text.

        Args:
            text: Raw text to preprocess

        Returns:
            PreprocessedDocument with cleaned text and extracted metadata
        """
        notes: list[str] = []
        original_text = text

        # Step 1: Unicode normalization
        if self.normalize_unicode:
            text = self._normalize_unicode(text)
            notes.append("Unicode normalized")

        # Step 2: Clean text
        text = self._clean_text(text)
        notes.append("Text cleaned")

        # Step 3: Remove headers/footers
        if self.remove_headers_footers:
            text = self._remove_headers_footers(text)
            notes.append("Headers/footers removed")

        # Step 4: Extract citations
        citations: list[Citation] = []
        if self.extract_citations:
            citations = self._extract_citations(text)
            notes.append(f"Extracted {len(citations)} citations")

        # Step 5: Detect sections
        sections: list[Section] = []
        if self.detect_sections:
            sections = self._detect_sections(text)
            notes.append(f"Detected {len(sections)} sections")

        # Step 6: Extract metadata
        effective_date = self._extract_effective_date(text)
        jurisdiction = self._detect_jurisdiction(text)
        regulation_type = self._detect_regulation_type(text)

        # Calculate statistics
        sentences = re.split(r"[.!?]+", text)
        sentence_count = len([s for s in sentences if s.strip()])
        word_count = len(text.split())

        logger.debug(
            "text_preprocessed",
            original_chars=len(original_text),
            cleaned_chars=len(text),
            sections=len(sections),
            citations=len(citations),
        )

        return PreprocessedDocument(
            cleaned_text=text,
            original_text=original_text,
            sections=sections,
            citations=citations,
            effective_date=effective_date,
            jurisdiction=jurisdiction,
            regulation_type=regulation_type,
            sentence_count=sentence_count,
            word_count=word_count,
            preprocessing_notes=notes,
        )

    def _normalize_unicode(self, text: str) -> str:
        """Normalize Unicode characters."""
        # NFKC normalization (compatibility + canonical)
        text = unicodedata.normalize("NFKC", text)

        # Replace common problematic characters
        replacements = {
            "\u2018": "'",  # Left single quote
            "\u2019": "'",  # Right single quote
            "\u201c": '"',  # Left double quote
            "\u201d": '"',  # Right double quote
            "\u2013": "-",  # En dash
            "\u2014": "-",  # Em dash
            "\u2026": "...",  # Ellipsis
            "\u00a0": " ",  # Non-breaking space
            "\u00ad": "",  # Soft hyphen
            "\u200b": "",  # Zero-width space
            "§": "Section ",  # Section symbol
            "¶": "Paragraph ",  # Paragraph symbol
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove control characters except newlines and tabs
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Remove excessive whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove page numbers (common patterns)
        text = re.sub(r"(?m)^\s*Page\s+\d+\s*(of\s+\d+)?\s*$", "", text)
        text = re.sub(r"(?m)^\s*-\s*\d+\s*-\s*$", "", text)

        # Clean up spacing around punctuation
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        text = re.sub(r"([.,;:!?])(?=[^\s\d])", r"\1 ", text)

        return text.strip()

    def _remove_headers_footers(self, text: str) -> str:
        """Remove repeated headers and footers."""
        lines = text.split("\n")

        if len(lines) < 20:
            return text

        # Find repeated lines (likely headers/footers)
        line_counts: dict[str, int] = {}
        for line in lines:
            line_clean = line.strip()
            if len(line_clean) > 10 and len(line_clean) < 200:
                line_counts[line_clean] = line_counts.get(line_clean, 0) + 1

        # Lines that appear more than 3 times are likely headers/footers
        repeated_lines = {line for line, count in line_counts.items() if count > 3}

        # Filter out repeated lines
        filtered_lines = [line for line in lines if line.strip() not in repeated_lines]

        return "\n".join(filtered_lines)

    def _extract_citations(self, text: str) -> list[Citation]:
        """Extract legal citations from text."""
        citations: list[Citation] = []

        for citation_type, pattern in self.CITATION_PATTERNS.items():
            for match in pattern.finditer(text):
                citation = Citation(
                    raw_text=match.group(0),
                    citation_type=citation_type,
                    identifier=match.group(1)
                    if match.lastindex and match.lastindex >= 1
                    else match.group(0),
                    section=match.group(2) if match.lastindex and match.lastindex >= 2 else None,
                )
                citations.append(citation)

        return citations

    def _detect_sections(self, text: str) -> list[Section]:
        """Detect document sections."""
        sections: list[Section] = []

        for pattern in self.SECTION_PATTERNS:
            for match in pattern.finditer(text):
                groups = match.groupdict()

                section = Section(
                    number=groups.get("number", ""),
                    title=groups.get("title", "").strip() if groups.get("title") else None,
                    content="",  # Will be filled in post-processing
                    start_pos=match.start(),
                    end_pos=match.end(),
                    level=self._determine_section_level(groups.get("type", "")),
                )
                sections.append(section)

        # Sort by position and fill content
        sections.sort(key=lambda s: s.start_pos)

        for i, section in enumerate(sections):
            # Content extends to the next section or end of document
            end_pos = sections[i + 1].start_pos if i + 1 < len(sections) else len(text)
            section.content = text[section.end_pos : end_pos].strip()

        return sections

    def _determine_section_level(self, section_type: str) -> int:
        """Determine hierarchy level from section type."""
        type_lower = section_type.lower() if section_type else ""
        levels = {
            "title": 1,
            "part": 2,
            "chapter": 2,
            "subpart": 3,
            "article": 3,
            "division": 3,
            "section": 4,
        }
        return levels.get(type_lower, 4)

    def _extract_effective_date(self, text: str) -> date | None:
        """Extract effective date from text."""
        from dateutil import parser as date_parser

        for pattern in self.DATE_PATTERNS:
            match = pattern.search(text[:5000])  # Check first 5000 chars
            if match:
                try:
                    date_str = match.group(1)
                    parsed = date_parser.parse(date_str, fuzzy=True)
                    return parsed.date()
                except Exception:
                    continue

        return None

    def _detect_jurisdiction(self, text: str) -> str | None:
        """Detect jurisdiction from text content."""
        text_lower = text[:10000].lower()

        # Check for jurisdiction indicators
        jurisdiction_patterns = {
            "US": ["united states", "u.s.", "federal register", "u.s.c.", "c.f.r."],
            "EU": [
                "european union",
                "regulation (eu)",
                "directive",
                "eur-lex",
                "european parliament",
            ],
            "UK": ["united kingdom", "uk parliament", "statutory instrument", "uk legislation"],
            "CA": ["canada", "canadian", "gazette", "statutes of canada"],
            "AU": ["australia", "australian", "commonwealth of australia"],
            "SG": ["singapore", "monetary authority of singapore", "mas"],
        }

        for jurisdiction, patterns in jurisdiction_patterns.items():
            if any(p in text_lower for p in patterns):
                return jurisdiction

        return None

    def _detect_regulation_type(self, text: str) -> str | None:
        """Detect regulation type from text content."""
        text_lower = text[:5000].lower()

        type_patterns = {
            "data_protection": ["personal data", "data protection", "privacy", "gdpr"],
            "financial": ["securities", "banking", "financial", "investment", "aml", "kyc"],
            "healthcare": ["hipaa", "medical", "healthcare", "patient", "clinical"],
            "environmental": ["environmental", "emission", "pollution", "climate"],
            "labor": ["employment", "labor", "worker", "wage", "discrimination"],
            "consumer": ["consumer protection", "product safety", "fair trading"],
            "tax": ["taxation", "tax", "revenue", "customs"],
            "trade": ["import", "export", "trade", "tariff", "customs"],
        }

        for reg_type, patterns in type_patterns.items():
            if any(p in text_lower for p in patterns):
                return reg_type

        return None
