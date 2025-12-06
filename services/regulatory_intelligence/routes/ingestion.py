"""
Ingestion Routes
================

API endpoints for regulatory document ingestion and parsing.

Version: 0.1.0
"""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, HttpUrl

from shared.auth import User, get_current_user
from shared.database.mongodb import get_mongodb
from shared.llm import get_llm_provider
from shared.logging import get_logger


logger = get_logger(__name__)

router = APIRouter()


class IngestionSource(str, Enum):
    """Types of ingestion sources."""

    URL = "url"
    FILE = "file"
    TEXT = "text"


class JobStatus(str, Enum):
    """Ingestion job status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionRequest(BaseModel):
    """Request model for regulatory document ingestion."""

    source_type: IngestionSource
    source_url: HttpUrl | None = None
    text_content: str | None = None
    jurisdiction: str = Field(..., description="Primary jurisdiction code")
    name: str | None = Field(default=None, description="Regulation name (optional)")

    # Processing options
    extract_requirements: bool = Field(
        default=True,
        description="Whether to extract individual requirements",
    )
    classify_tiers: bool = Field(
        default=True,
        description="Whether to classify requirements by tier",
    )


class IngestionJob(BaseModel):
    """Ingestion job status model."""

    id: str
    status: JobStatus
    source_type: IngestionSource
    jurisdiction: str

    # Progress
    progress: dict[str, Any] = Field(default_factory=dict)

    # Result (when completed)
    result: dict[str, Any] | None = None
    error: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ParsedRequirement(BaseModel):
    """A requirement extracted from regulatory text."""

    article_ref: str
    text: str
    tier: str = "basic"
    verification_method: str = "self_attestation"


@router.post("", response_model=IngestionJob, status_code=status.HTTP_202_ACCEPTED)
async def start_ingestion(
    request: IngestionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
    current_user: User = Depends(get_current_user),
) -> IngestionJob:
    """
    Start a regulatory document ingestion job.

    The job runs in the background. Use GET /ingest/{job_id} to check status.

    Requires authentication.
    """
    # Validate request
    if request.source_type == IngestionSource.URL and not request.source_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_url required for URL ingestion",
        )
    if request.source_type == IngestionSource.TEXT and not request.text_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="text_content required for text ingestion",
        )

    # Create job
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job = IngestionJob(
        id=job_id,
        status=JobStatus.PENDING,
        source_type=request.source_type,
        jurisdiction=request.jurisdiction.upper(),
        progress={"current_step": "queued", "total_steps": 4, "completed_steps": 0},
    )

    # Store job in MongoDB
    await db.ingestion_jobs.insert_one(
        {
            "_id": job_id,
            **job.model_dump(mode="json"),
        }
    )

    # Start background processing
    background_tasks.add_task(
        process_ingestion_job,
        job_id,
        request,
        current_user.id,
    )

    logger.info(
        "ingestion_job_created",
        job_id=job_id,
        source_type=request.source_type.value,
        user_id=current_user.id,
    )

    return job


@router.get("/{job_id}", response_model=IngestionJob)
async def get_ingestion_job(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
) -> IngestionJob:
    """
    Get ingestion job status.

    Args:
        job_id: Job ID returned from POST /ingest
    """
    doc = await db.ingestion_jobs.find_one({"_id": job_id})

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return IngestionJob(
        id=doc["_id"],
        status=JobStatus(doc["status"]),
        source_type=IngestionSource(doc["source_type"]),
        jurisdiction=doc["jurisdiction"],
        progress=doc.get("progress", {}),
        result=doc.get("result"),
        error=doc.get("error"),
        created_at=doc.get("created_at"),
        started_at=doc.get("started_at"),
        completed_at=doc.get("completed_at"),
    )


@router.post("/parse-text", response_model=list[ParsedRequirement])
async def parse_regulatory_text(
    text: str,
    jurisdiction: str,
    current_user: User = Depends(get_current_user),
) -> list[ParsedRequirement]:
    """
    Parse regulatory text and extract requirements using LLM.

    This is a synchronous endpoint for quick parsing of small texts.
    For large documents, use the async ingestion endpoint.

    Requires authentication.
    """
    if len(text) > 50000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text too long. Use async ingestion for large documents.",
        )

    requirements = await extract_requirements_with_llm(text, jurisdiction)

    logger.info(
        "text_parsed",
        jurisdiction=jurisdiction,
        requirements_count=len(requirements),
        user_id=current_user.id,
    )

    return requirements


# ============================================================================
# Background Processing
# ============================================================================


async def process_ingestion_job(
    job_id: str,
    request: IngestionRequest,
    user_id: str,
) -> None:
    """
    Process an ingestion job in the background.

    Steps:
    1. Fetch/extract document content
    2. Parse regulatory structure
    3. Extract requirements
    4. Store in database
    """
    from shared.database.mongodb import MongoDBClient

    db = MongoDBClient.get_database()

    try:
        # Update status to processing
        await db.ingestion_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.PROCESSING.value,
                    "started_at": datetime.now(UTC),
                    "progress.current_step": "fetching",
                    "progress.completed_steps": 1,
                }
            },
        )

        # Step 1: Get document content
        if request.source_type == IngestionSource.TEXT:
            content = request.text_content or ""
        elif request.source_type == IngestionSource.URL:
            content = await fetch_url_content(str(request.source_url))
        else:
            raise ValueError(f"Unsupported source type: {request.source_type}")

        # Update progress
        await db.ingestion_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "progress.current_step": "parsing",
                    "progress.completed_steps": 2,
                }
            },
        )

        # Step 2: Extract requirements using LLM
        requirements = []
        if request.extract_requirements:
            requirements = await extract_requirements_with_llm(
                content,
                request.jurisdiction,
            )

        # Update progress
        await db.ingestion_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "progress.current_step": "storing",
                    "progress.completed_steps": 3,
                }
            },
        )

        # Step 3: Store regulation and requirements
        regulation_id = f"REG-{request.jurisdiction}-{uuid.uuid4().hex[:8].upper()}"

        # Create regulation document
        regulation_doc = {
            "_id": regulation_id,
            "name": request.name or f"Regulation from {request.source_type.value}",
            "jurisdiction": request.jurisdiction.upper(),
            "jurisdictions": [request.jurisdiction.upper()],
            "sectors": [],
            "effective_date": datetime.now(UTC),
            "source_url": str(request.source_url) if request.source_url else None,
            "raw_text": content[:100000],  # Truncate if very long
            "rml": {
                "version": "1.0",
                "requirements_count": len(requirements),
            },
            "parsing_metadata": {
                "parser_version": "0.1.0",
                "model_used": "llm",
                "parsed_at": datetime.now(UTC),
            },
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        await db.regulations.insert_one(regulation_doc)

        # Store requirements
        for i, req in enumerate(requirements):
            req_id = f"REQ-{regulation_id[4:]}-{i + 1}"
            req_doc = {
                "_id": req_id,
                "regulation_id": regulation_id,
                "article_ref": req.article_ref,
                "natural_language": req.text,
                "tier": req.tier,
                "verification_method": req.verification_method,
                "parsing_metadata": {
                    "parser_version": "0.1.0",
                    "model_used": "llm",
                },
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
            await db.requirements.insert_one(req_doc)

        # Mark job as completed
        await db.ingestion_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.COMPLETED.value,
                    "completed_at": datetime.now(UTC),
                    "progress.current_step": "completed",
                    "progress.completed_steps": 4,
                    "result": {
                        "regulation_id": regulation_id,
                        "requirements_count": len(requirements),
                    },
                }
            },
        )

        logger.info(
            "ingestion_job_completed",
            job_id=job_id,
            regulation_id=regulation_id,
            requirements_count=len(requirements),
        )

    except Exception as e:
        logger.error(
            "ingestion_job_failed",
            job_id=job_id,
            error=str(e),
        )

        await db.ingestion_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.FAILED.value,
                    "completed_at": datetime.now(UTC),
                    "error": str(e),
                }
            },
        )


async def fetch_url_content(url: str) -> str:
    """Fetch content from a URL."""
    import httpx

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def extract_requirements_with_llm(
    text: str,
    jurisdiction: str,
) -> list[ParsedRequirement]:
    """
    Extract requirements from regulatory text using LLM.

    Args:
        text: Regulatory text to parse
        jurisdiction: Jurisdiction code

    Returns:
        List of extracted requirements
    """
    provider = get_llm_provider()

    system_prompt = """You are an expert regulatory analyst. Your task is to extract individual compliance requirements from regulatory text.

For each requirement, identify:
1. Article/section reference
2. The requirement text
3. Compliance tier (basic, standard, or advanced based on complexity)
4. Verification method (self_attestation, document_review, cryptographic_proof, or on_site_audit)

Respond ONLY with valid JSON array. No markdown, no explanation."""

    user_prompt = f"""Extract compliance requirements from this {jurisdiction} regulatory text:

---
{text[:15000]}
---

Return a JSON array with objects containing: article_ref, text, tier, verification_method"""

    try:
        result = await provider.generate_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
        )

        # Parse result
        requirements = []
        if isinstance(result, list):
            for item in result:
                requirements.append(
                    ParsedRequirement(
                        article_ref=item.get("article_ref", "Unknown"),
                        text=item.get("text", ""),
                        tier=item.get("tier", "basic"),
                        verification_method=item.get("verification_method", "self_attestation"),
                    )
                )

        return requirements

    except Exception as e:
        logger.error("llm_extraction_failed", error=str(e))
        return []
