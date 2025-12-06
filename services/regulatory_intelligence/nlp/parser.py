"""
Regulatory Parser Module
========================

LLM-based parser for extracting structured requirements
from regulatory text.

Features:
- Requirement extraction and classification
- Tier assignment (Basic/Standard/Advanced)
- Formal logic generation
- Penalty extraction
- Cross-reference resolution

Version: 0.1.0
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

from services.regulatory_intelligence.nlp.chunking import Chunk, DocumentChunker
from shared.llm import LLMMessage, get_llm_provider
from shared.logging import get_logger


logger = get_logger(__name__)


class RequirementType(str, Enum):
    """Types of regulatory requirements."""

    OBLIGATION = "obligation"  # Must do something
    PROHIBITION = "prohibition"  # Must not do something
    PERMISSION = "permission"  # May do something
    CONDITION = "condition"  # If X then Y
    DEFINITION = "definition"  # Defines a term
    PROCEDURE = "procedure"  # Describes a process
    RECORD_KEEPING = "record_keeping"  # Documentation requirements
    REPORTING = "reporting"  # Reporting obligations
    EXCEPTION = "exception"  # Exemption or exception


class ComplianceTier(str, Enum):
    """Compliance complexity tiers."""

    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"


class VerificationMethod(str, Enum):
    """Methods for verifying compliance."""

    SELF_ATTESTATION = "self_attestation"
    DOCUMENT_REVIEW = "document_review"
    CRYPTOGRAPHIC_PROOF = "cryptographic_proof"
    ON_SITE_AUDIT = "on_site_audit"
    AUTOMATED_MONITORING = "automated_monitoring"


@dataclass
class ParsedRequirement:
    """A single parsed requirement."""

    # Identification
    id: str
    article_ref: str
    regulation_id: str

    # Content
    natural_language: str
    summary: str | None = None
    formal_logic: str | None = None

    # Classification
    requirement_type: RequirementType = RequirementType.OBLIGATION
    tier: ComplianceTier = ComplianceTier.BASIC
    verification_method: VerificationMethod = VerificationMethod.SELF_ATTESTATION

    # Applicability
    applies_to: list[str] = field(default_factory=list)  # Entity types
    sectors: list[str] = field(default_factory=list)
    jurisdictions: list[str] = field(default_factory=list)

    # Penalties
    penalty_monetary_max: float | None = None
    penalty_formula: str | None = None
    penalty_imprisonment_max: float | None = None

    # Dates
    effective_date: date | None = None
    sunset_date: date | None = None

    # Cross-references
    references: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    conflicts_with: list[str] = field(default_factory=list)

    # Confidence
    confidence: float = 0.0
    parsing_notes: list[str] = field(default_factory=list)


@dataclass
class ParsedRegulation:
    """A fully parsed regulation."""

    id: str
    name: str
    short_name: str | None = None

    jurisdiction: str = ""
    jurisdictions: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)

    effective_date: date | None = None
    sunset_date: date | None = None

    requirements: list[ParsedRequirement] = field(default_factory=list)

    # Parsing metadata
    source_url: str | None = None
    source_hash: str | None = None
    total_chunks: int = 0
    processing_time_seconds: float = 0.0
    parsing_notes: list[str] = field(default_factory=list)


class RegulatoryParser:
    """
    LLM-based parser for regulatory documents.

    Extracts structured requirements using multi-step prompting:
    1. Initial requirement identification
    2. Classification and tier assignment
    3. Formal logic conversion
    4. Cross-reference resolution
    """

    # System prompts for different parsing stages
    EXTRACTION_PROMPT = """You are an expert regulatory analyst. Your task is to extract individual compliance requirements from regulatory text.

For each distinct requirement, identify:
1. The article/section reference (e.g., "Article 6(1)(a)" or "Section 3.2")
2. The exact requirement text
3. Whether it's an obligation (must do), prohibition (must not), permission (may), condition, definition, procedure, record-keeping, reporting, or exception
4. Who it applies to (data controllers, financial institutions, employers, etc.)

IMPORTANT RULES:
- Each requirement should be atomic and testable
- Split compound requirements into separate items
- Include the full context needed to understand the requirement
- Preserve legal language accurately
- Note any conditions or exceptions

Respond with a JSON array of requirements. Each requirement should have:
- article_ref: string
- text: string
- type: "obligation" | "prohibition" | "permission" | "condition" | "definition" | "procedure" | "record_keeping" | "reporting" | "exception"
- applies_to: string[] (entity types this applies to)
- conditions: string[] (any conditions that must be met)"""

    CLASSIFICATION_PROMPT = """You are a compliance expert. Classify the following regulatory requirement.

Determine:
1. TIER (complexity level):
   - basic: Simple, clear requirements that most entities can easily comply with
   - standard: Moderate complexity, may require some expertise or documentation
   - advanced: Complex requirements needing specialized systems, audits, or expertise

2. VERIFICATION METHOD (how compliance would be verified):
   - self_attestation: Entity declares compliance
   - document_review: Reviewing policies, procedures, records
   - cryptographic_proof: Cryptographic evidence (hashes, signatures, ZK proofs)
   - on_site_audit: Physical inspection or audit
   - automated_monitoring: Continuous automated checks

3. SECTORS this primarily applies to (if specific):
   - FINANCE, HEALTH, TECH, ENERGY, MANUFACTURING, RETAIL, TRANSPORT, GOVERNMENT, or ALL

4. PENALTY indicators if mentioned (monetary amounts, imprisonment terms)

Respond with JSON:
{
  "tier": "basic" | "standard" | "advanced",
  "verification_method": "self_attestation" | "document_review" | "cryptographic_proof" | "on_site_audit" | "automated_monitoring",
  "sectors": string[],
  "penalty_monetary_max": number | null,
  "penalty_formula": string | null,
  "rationale": string
}"""

    FORMAL_LOGIC_PROMPT = """You are a formal methods expert. Convert this regulatory requirement into formal logic notation.

Use this notation:
- FORALL x: ... (universal quantification)
- EXISTS x: ... (existential quantification)
- P -> Q (implication: if P then Q)
- P & Q (conjunction: P and Q)
- P | Q (disjunction: P or Q)
- ~P (negation: not P)
- P <-> Q (biconditional: P if and only if Q)

Predicates should be descriptive, e.g.:
- has_consent(subject, purpose)
- processes_data(controller, data)
- within_timeframe(action, days)
- maintains_record(entity, record_type)

Respond with JSON:
{
  "formal_logic": string,
  "predicates": [{"name": string, "description": string}],
  "notes": string
}"""

    def __init__(
        self,
        max_concurrent_requests: int = 5,
        chunk_size: int = 4000,
        enable_formal_logic: bool = True,
    ) -> None:
        """
        Initialize the parser.

        Args:
            max_concurrent_requests: Max concurrent LLM requests
            chunk_size: Target chunk size for processing
            enable_formal_logic: Whether to generate formal logic
        """
        self.max_concurrent_requests = max_concurrent_requests
        self.chunk_size = chunk_size
        self.enable_formal_logic = enable_formal_logic

        self.chunker = DocumentChunker(max_chunk_size=chunk_size)
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def parse_document(
        self,
        text: str,
        regulation_id: str,
        regulation_name: str,
        jurisdiction: str,
        metadata: dict[str, Any] | None = None,
    ) -> ParsedRegulation:
        """
        Parse a complete regulatory document.

        Args:
            text: Document text to parse
            regulation_id: ID for the regulation
            regulation_name: Name of the regulation
            jurisdiction: Primary jurisdiction
            metadata: Additional metadata

        Returns:
            ParsedRegulation with extracted requirements
        """
        import time

        start_time = time.perf_counter()
        parsing_notes: list[str] = []

        # Chunk the document
        chunks = self.chunker.chunk(text)
        parsing_notes.append(f"Document split into {len(chunks)} chunks")

        logger.info(
            "parsing_document",
            regulation_id=regulation_id,
            chunks=len(chunks),
            chars=len(text),
        )

        # Extract requirements from each chunk in parallel
        all_requirements: list[ParsedRequirement] = []
        tasks = [self._parse_chunk(chunk, regulation_id, jurisdiction) for chunk in chunks]

        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(chunk_results):
            if isinstance(result, Exception):
                parsing_notes.append(f"Chunk {i} failed: {result!s}")
                logger.error("chunk_parsing_failed", chunk=i, error=str(result))
            else:
                all_requirements.extend(result)

        # Deduplicate requirements
        requirements = self._deduplicate_requirements(all_requirements)
        parsing_notes.append(
            f"Extracted {len(all_requirements)} requirements, "
            f"{len(requirements)} after deduplication"
        )

        # Assign IDs
        for i, req in enumerate(requirements):
            req.id = f"REQ-{regulation_id[4:]}-{i + 1:03d}"

        processing_time = time.perf_counter() - start_time

        logger.info(
            "document_parsed",
            regulation_id=regulation_id,
            requirements=len(requirements),
            processing_time=f"{processing_time:.2f}s",
        )

        return ParsedRegulation(
            id=regulation_id,
            name=regulation_name,
            jurisdiction=jurisdiction,
            jurisdictions=[jurisdiction],
            requirements=requirements,
            total_chunks=len(chunks),
            processing_time_seconds=processing_time,
            parsing_notes=parsing_notes,
        )

    async def _parse_chunk(
        self,
        chunk: Chunk,
        regulation_id: str,
        jurisdiction: str,
    ) -> list[ParsedRequirement]:
        """Parse a single chunk."""
        async with self._semaphore:
            requirements: list[ParsedRequirement] = []

            try:
                # Step 1: Extract requirements
                extracted = await self._extract_requirements(chunk.content)

                for item in extracted:
                    req = ParsedRequirement(
                        id="",  # Will be assigned later
                        article_ref=item.get("article_ref", "Unknown"),
                        regulation_id=regulation_id,
                        natural_language=item.get("text", ""),
                        requirement_type=RequirementType(item.get("type", "obligation")),
                        applies_to=item.get("applies_to", []),
                        jurisdictions=[jurisdiction],
                    )

                    # Step 2: Classify requirement
                    classification = await self._classify_requirement(req.natural_language)
                    req.tier = ComplianceTier(classification.get("tier", "basic"))
                    req.verification_method = VerificationMethod(
                        classification.get("verification_method", "self_attestation")
                    )
                    req.sectors = classification.get("sectors", [])
                    req.penalty_monetary_max = classification.get("penalty_monetary_max")
                    req.penalty_formula = classification.get("penalty_formula")
                    req.confidence = 0.8

                    # Step 3: Generate formal logic (if enabled)
                    if self.enable_formal_logic:
                        try:
                            formal = await self._generate_formal_logic(req.natural_language)
                            req.formal_logic = formal.get("formal_logic")
                        except Exception as e:
                            req.parsing_notes.append(f"Formal logic generation failed: {e}")

                    requirements.append(req)

            except Exception as e:
                logger.error(
                    "chunk_extraction_failed",
                    chunk_index=chunk.index,
                    error=str(e),
                )
                raise

            return requirements

    async def _extract_requirements(self, text: str) -> list[dict[str, Any]]:
        """Extract requirements from text using LLM."""
        provider = get_llm_provider()

        messages = [
            LLMMessage(role="system", content=self.EXTRACTION_PROMPT),
            LLMMessage(
                role="user",
                content=f"Extract requirements from this regulatory text:\n\n{text}",
            ),
        ]

        response = await provider.complete(messages, temperature=0.1)

        # Parse JSON response
        try:
            return self._parse_json_response(response.content)
        except Exception as e:
            logger.warning("json_parse_failed", error=str(e))
            return []

    async def _classify_requirement(self, text: str) -> dict[str, Any]:
        """Classify a requirement using LLM."""
        provider = get_llm_provider()

        messages = [
            LLMMessage(role="system", content=self.CLASSIFICATION_PROMPT),
            LLMMessage(role="user", content=f"Classify this requirement:\n\n{text}"),
        ]

        response = await provider.complete(messages, temperature=0.1)

        try:
            result = self._parse_json_object(response.content)
            return result
        except Exception as e:
            logger.warning("classification_parse_failed", error=str(e))
            return {"tier": "basic", "verification_method": "self_attestation"}

    async def _generate_formal_logic(self, text: str) -> dict[str, Any]:
        """Generate formal logic representation."""
        provider = get_llm_provider()

        messages = [
            LLMMessage(role="system", content=self.FORMAL_LOGIC_PROMPT),
            LLMMessage(
                role="user",
                content=f"Convert to formal logic:\n\n{text}",
            ),
        ]

        response = await provider.complete(messages, temperature=0.1)

        try:
            return self._parse_json_object(response.content)
        except Exception:
            return {"formal_logic": None}

    def _parse_json_response(self, text: str) -> list[dict[str, Any]]:
        """Parse JSON array from LLM response."""
        # Clean up response
        text = text.strip()

        # Remove markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        # Try to find JSON array
        start = text.find("[")
        end = text.rfind("]") + 1

        if start >= 0 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)

        return []

    def _parse_json_object(self, text: str) -> dict[str, Any]:
        """Parse JSON object from LLM response."""
        text = text.strip()

        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        start = text.find("{")
        end = text.rfind("}") + 1

        if start >= 0 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)

        return {}

    def _deduplicate_requirements(
        self,
        requirements: list[ParsedRequirement],
    ) -> list[ParsedRequirement]:
        """Remove duplicate requirements based on text similarity."""
        if not requirements:
            return []

        unique: list[ParsedRequirement] = []
        seen_texts: set[str] = set()

        for req in requirements:
            # Normalize text for comparison
            normalized = re.sub(r"\s+", " ", req.natural_language.lower().strip())

            # Check for near-duplicates
            is_duplicate = False
            for seen in seen_texts:
                if self._text_similarity(normalized, seen) > 0.9:
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen_texts.add(normalized)
                unique.append(req)

        return unique

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity (Jaccard on words)."""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    async def parse_single_requirement(
        self,
        text: str,
        article_ref: str,
        regulation_id: str,
    ) -> ParsedRequirement:
        """
        Parse a single requirement text.

        Useful for manual input or corrections.
        """
        req = ParsedRequirement(
            id=f"REQ-{regulation_id}-manual",
            article_ref=article_ref,
            regulation_id=regulation_id,
            natural_language=text,
        )

        # Classify
        classification = await self._classify_requirement(text)
        req.tier = ComplianceTier(classification.get("tier", "basic"))
        req.verification_method = VerificationMethod(
            classification.get("verification_method", "self_attestation")
        )
        req.sectors = classification.get("sectors", [])

        # Formal logic
        if self.enable_formal_logic:
            formal = await self._generate_formal_logic(text)
            req.formal_logic = formal.get("formal_logic")

        req.confidence = 0.9
        return req
