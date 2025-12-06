"""
NLP Pipeline Routes
===================

Complete regulatory document processing pipeline.

Integrates:
- Document extraction
- Text preprocessing
- LLM-based parsing
- RML generation
- Embedding generation
- Storage

Version: 0.1.0
"""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, HttpUrl

from services.regulatory_intelligence.nlp.chunking import ChunkingStrategy
from services.regulatory_intelligence.nlp.embeddings import EmbeddingService
from services.regulatory_intelligence.nlp.extraction import DocumentExtractor
from services.regulatory_intelligence.nlp.parser import RegulatoryParser
from services.regulatory_intelligence.nlp.preprocessing import TextPreprocessor
from services.regulatory_intelligence.nlp.rml import RMLGenerator
from shared.auth import User, get_current_user
from shared.database.kafka import KafkaClient, Topics
from shared.database.mongodb import get_mongodb
from shared.logging import get_logger


logger = get_logger(__name__)

router = APIRouter()


class PipelineStatus(str, Enum):
    """Pipeline job status."""

    QUEUED = "queued"
    EXTRACTING = "extracting"
    PREPROCESSING = "preprocessing"
    PARSING = "parsing"
    GENERATING_RML = "generating_rml"
    GENERATING_EMBEDDINGS = "generating_embeddings"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineConfig(BaseModel):
    """Configuration for pipeline execution."""

    # Extraction options
    extract_from_url: bool = True

    # Preprocessing options
    normalize_unicode: bool = True
    extract_citations: bool = True
    detect_sections: bool = True

    # Chunking options
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE
    max_chunk_size: int = Field(default=4000, ge=1000, le=16000)

    # Parsing options
    extract_requirements: bool = True
    enable_formal_logic: bool = True
    max_concurrent_requests: int = Field(default=5, ge=1, le=20)

    # Embedding options
    generate_embeddings: bool = True

    # Storage options
    store_raw_text: bool = True
    store_rml: bool = True


class PipelineRequest(BaseModel):
    """Request to run the regulatory pipeline."""

    # Source
    source_url: HttpUrl | None = None
    text_content: str | None = None

    # Regulation metadata
    regulation_name: str = Field(..., min_length=1, max_length=500)
    jurisdiction: str = Field(..., min_length=2, max_length=10)
    short_name: str | None = Field(default=None, max_length=50)

    # Configuration
    config: PipelineConfig = Field(default_factory=PipelineConfig)


class PipelineJobStatus(BaseModel):
    """Status of a pipeline job."""

    job_id: str
    status: PipelineStatus
    progress: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None

    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class PipelineResult(BaseModel):
    """Result of pipeline execution."""

    regulation_id: str
    name: str
    jurisdiction: str

    # Statistics
    total_requirements: int
    requirements_by_tier: dict[str, int]

    # Processing info
    chunks_processed: int
    processing_time_seconds: float

    # References
    rml_document_id: str | None = None
    embeddings_count: int = 0


@router.post("/run", response_model=PipelineJobStatus, status_code=status.HTTP_202_ACCEPTED)
async def run_pipeline(
    request: PipelineRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
    current_user: User = Depends(get_current_user),
) -> PipelineJobStatus:
    """
    Run the complete regulatory processing pipeline.

    This endpoint processes a regulatory document through all stages:
    1. Extraction (URL or text)
    2. Preprocessing (cleaning, normalization)
    3. Parsing (requirement extraction with LLM)
    4. RML generation
    5. Embedding generation
    6. Storage

    The pipeline runs asynchronously. Use GET /pipeline/{job_id} to check status.

    Requires authentication.
    """
    # Validate input
    if not request.source_url and not request.text_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either source_url or text_content is required",
        )

    # Create job
    job_id = f"pipeline_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC)

    job_status = PipelineJobStatus(
        job_id=job_id,
        status=PipelineStatus.QUEUED,
        progress={
            "current_step": "queued",
            "steps_completed": 0,
            "total_steps": 6,
        },
        created_at=now,
    )

    # Store job in MongoDB
    await db.pipeline_jobs.insert_one(
        {
            "_id": job_id,
            "status": job_status.status.value,
            "progress": job_status.progress,
            "request": request.model_dump(mode="json"),
            "user_id": current_user.id,
            "created_at": now,
        }
    )

    # Start background processing
    background_tasks.add_task(
        execute_pipeline,
        job_id,
        request,
        current_user.id,
    )

    logger.info(
        "pipeline_job_created",
        job_id=job_id,
        regulation=request.regulation_name,
        user_id=current_user.id,
    )

    return job_status


@router.get("/{job_id}", response_model=PipelineJobStatus)
async def get_pipeline_status(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
) -> PipelineJobStatus:
    """
    Get pipeline job status.

    Args:
        job_id: Pipeline job ID
    """
    doc = await db.pipeline_jobs.find_one({"_id": job_id})

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline job not found: {job_id}",
        )

    return PipelineJobStatus(
        job_id=job_id,
        status=PipelineStatus(doc["status"]),
        progress=doc.get("progress", {}),
        result=doc.get("result"),
        error=doc.get("error"),
        created_at=doc.get("created_at"),
        started_at=doc.get("started_at"),
        completed_at=doc.get("completed_at"),
    )


@router.get("", response_model=list[PipelineJobStatus])
async def list_pipeline_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: PipelineStatus | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
    current_user: User = Depends(get_current_user),
) -> list[PipelineJobStatus]:
    """
    List pipeline jobs for the current user.

    Requires authentication.
    """
    query: dict[str, Any] = {"user_id": current_user.id}
    if status_filter:
        query["status"] = status_filter.value

    cursor = db.pipeline_jobs.find(query).sort("created_at", -1).limit(limit)

    jobs = []
    async for doc in cursor:
        jobs.append(
            PipelineJobStatus(
                job_id=doc["_id"],
                status=PipelineStatus(doc["status"]),
                progress=doc.get("progress", {}),
                result=doc.get("result"),
                error=doc.get("error"),
                created_at=doc.get("created_at"),
                started_at=doc.get("started_at"),
                completed_at=doc.get("completed_at"),
            )
        )

    return jobs


# ============================================================================
# Pipeline Execution
# ============================================================================


async def execute_pipeline(
    job_id: str,
    request: PipelineRequest,
    user_id: str,
) -> None:
    """
    Execute the complete pipeline.

    This runs in the background after the API returns.
    """
    import time

    from shared.database.mongodb import MongoDBClient

    db = MongoDBClient.get_database()
    start_time = time.perf_counter()

    async def update_status(
        status: PipelineStatus,
        step: str,
        steps_completed: int,
    ) -> None:
        """Update job status in database."""
        await db.pipeline_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": status.value,
                    "progress.current_step": step,
                    "progress.steps_completed": steps_completed,
                    "started_at": datetime.now(UTC) if steps_completed == 1 else None,
                }
            },
        )

    try:
        # Step 1: Extraction
        await update_status(PipelineStatus.EXTRACTING, "extracting", 1)

        extractor = DocumentExtractor()
        if request.source_url:
            extraction_result = await extractor.extract_from_url(str(request.source_url))
        else:
            from services.regulatory_intelligence.nlp.extraction import (
                DocumentFormat,
                ExtractionResult,
            )

            extraction_result = ExtractionResult(
                content=request.text_content or "",
                format=DocumentFormat.TEXT,
            )

        logger.debug(
            "pipeline_extraction_complete",
            job_id=job_id,
            chars=len(extraction_result.content),
        )

        # Step 2: Preprocessing
        await update_status(PipelineStatus.PREPROCESSING, "preprocessing", 2)

        preprocessor = TextPreprocessor(
            normalize_unicode=request.config.normalize_unicode,
            extract_citations=request.config.extract_citations,
            detect_sections=request.config.detect_sections,
        )
        preprocessed = preprocessor.preprocess(extraction_result.content)

        logger.debug(
            "pipeline_preprocessing_complete",
            job_id=job_id,
            sections=len(preprocessed.sections),
            citations=len(preprocessed.citations),
        )

        # Step 3: Parsing
        await update_status(PipelineStatus.PARSING, "parsing", 3)

        regulation_id = f"REG-{request.jurisdiction.upper()}-{uuid.uuid4().hex[:8].upper()}"

        parser = RegulatoryParser(
            max_concurrent_requests=request.config.max_concurrent_requests,
            chunk_size=request.config.max_chunk_size,
            enable_formal_logic=request.config.enable_formal_logic,
        )

        parsed = await parser.parse_document(
            text=preprocessed.cleaned_text,
            regulation_id=regulation_id,
            regulation_name=request.regulation_name,
            jurisdiction=request.jurisdiction.upper(),
        )

        logger.debug(
            "pipeline_parsing_complete",
            job_id=job_id,
            requirements=len(parsed.requirements),
        )

        # Step 4: RML Generation
        await update_status(PipelineStatus.GENERATING_RML, "generating_rml", 4)

        rml_generator = RMLGenerator(include_formal_logic=request.config.enable_formal_logic)
        rml_doc = rml_generator.generate(
            regulation=parsed,
            source_url=str(request.source_url) if request.source_url else None,
            source_hash=extraction_result.content_hash,
        )

        # Validate RML
        validation_errors = rml_generator.validate(rml_doc)
        if validation_errors:
            logger.warning(
                "rml_validation_errors",
                job_id=job_id,
                errors=validation_errors,
            )

        # Step 5: Embeddings
        embeddings_count = 0
        if request.config.generate_embeddings:
            await update_status(PipelineStatus.GENERATING_EMBEDDINGS, "generating_embeddings", 5)

            try:
                embedding_service = EmbeddingService()
                texts = [req.natural_language for req in parsed.requirements]

                if texts:
                    embeddings = await embedding_service.embed_texts(texts)
                    embeddings_count = len(embeddings)

                    # Store embeddings (would go to vector database in production)
                    for req, emb in zip(parsed.requirements, embeddings):
                        await db.requirement_embeddings.update_one(
                            {"requirement_id": req.id},
                            {
                                "$set": {
                                    "requirement_id": req.id,
                                    "regulation_id": regulation_id,
                                    "embedding": emb.embedding,
                                    "model": emb.model,
                                    "updated_at": datetime.now(UTC),
                                }
                            },
                            upsert=True,
                        )

                logger.debug(
                    "pipeline_embeddings_complete",
                    job_id=job_id,
                    count=embeddings_count,
                )

            except Exception as e:
                logger.error("embeddings_failed", error=str(e))
                # Continue without embeddings

        # Step 6: Storage
        await update_status(PipelineStatus.STORING, "storing", 6)

        # Store regulation
        regulation_doc = {
            "_id": regulation_id,
            "name": request.regulation_name,
            "short_name": request.short_name,
            "jurisdiction": request.jurisdiction.upper(),
            "jurisdictions": [request.jurisdiction.upper()],
            "sectors": [],
            "effective_date": preprocessed.effective_date,
            "source_url": str(request.source_url) if request.source_url else None,
            "source_hash": extraction_result.content_hash,
            "raw_text": preprocessed.cleaned_text if request.config.store_raw_text else None,
            "rml": rml_doc.to_dict() if request.config.store_rml else None,
            "parsing_metadata": {
                "parser_version": "0.1.0",
                "model_used": "llm",
                "chunks_processed": parsed.total_chunks,
                "processing_time": parsed.processing_time_seconds,
                "parsed_at": datetime.now(UTC),
            },
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        await db.regulations.replace_one(
            {"_id": regulation_id},
            regulation_doc,
            upsert=True,
        )

        # Store requirements
        for req in parsed.requirements:
            req_doc = {
                "_id": req.id,
                "regulation_id": regulation_id,
                "article_ref": req.article_ref,
                "natural_language": req.natural_language,
                "summary": req.summary,
                "formal_logic": req.formal_logic,
                "tier": req.tier.value,
                "verification_method": req.verification_method.value,
                "requirement_type": req.requirement_type.value,
                "sectors": req.sectors,
                "applies_to": req.applies_to,
                "penalty": {
                    "monetary_max": req.penalty_monetary_max,
                    "formula": req.penalty_formula,
                    "imprisonment_max": req.penalty_imprisonment_max,
                }
                if req.penalty_monetary_max or req.penalty_formula
                else None,
                "parsing_metadata": {
                    "confidence": req.confidence,
                    "notes": req.parsing_notes,
                },
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }

            await db.requirements.replace_one(
                {"_id": req.id},
                req_doc,
                upsert=True,
            )

        # Calculate statistics
        by_tier = {"basic": 0, "standard": 0, "advanced": 0}
        for req in parsed.requirements:
            tier = req.tier.value
            if tier in by_tier:
                by_tier[tier] += 1

        processing_time = time.perf_counter() - start_time

        # Build result
        result = {
            "regulation_id": regulation_id,
            "name": request.regulation_name,
            "jurisdiction": request.jurisdiction.upper(),
            "total_requirements": len(parsed.requirements),
            "requirements_by_tier": by_tier,
            "chunks_processed": parsed.total_chunks,
            "processing_time_seconds": round(processing_time, 2),
            "embeddings_count": embeddings_count,
        }

        # Mark job completed
        await db.pipeline_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": PipelineStatus.COMPLETED.value,
                    "progress.current_step": "completed",
                    "progress.steps_completed": 6,
                    "result": result,
                    "completed_at": datetime.now(UTC),
                }
            },
        )

        # Publish completion event
        try:
            await KafkaClient.publish(
                topic=Topics.REGULATORY_CHANGES,
                value={
                    "event_type": "regulation_processed",
                    "regulation_id": regulation_id,
                    "name": request.regulation_name,
                    "requirements_count": len(parsed.requirements),
                    "processed_at": datetime.now(UTC).isoformat(),
                },
                key=regulation_id,
            )
        except Exception as e:
            logger.warning("kafka_publish_failed", error=str(e))

        logger.info(
            "pipeline_completed",
            job_id=job_id,
            regulation_id=regulation_id,
            requirements=len(parsed.requirements),
            time=f"{processing_time:.2f}s",
        )

    except Exception as e:
        logger.error(
            "pipeline_failed",
            job_id=job_id,
            error=str(e),
            error_type=type(e).__name__,
        )

        await db.pipeline_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": PipelineStatus.FAILED.value,
                    "error": str(e),
                    "completed_at": datetime.now(UTC),
                }
            },
        )
