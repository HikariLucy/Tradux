"""API endpoints for asynchronous translation job management."""

import json
import logging
from pathlib import Path
from typing import Annotated

import pymupdf
from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)

from app.core.config import get_settings
from app.jobs.models import (
    SUPPORTED_LANGUAGES,
    JobCreateResponse,
    JobMode,
    JobResponse,
    JobStatus,
)
from app.jobs.service import (
    ProviderNotConfiguredError,
    get_job_service,
)
from app.jobs.store import get_job_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _parse_protected_terms(raw: str | None) -> list[str]:
    """Parse protected terms string safely."""
    if not raw or not raw.strip():
        return []
    stripped = raw.strip()
    # Check if JSON list format
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            data = json.loads(stripped)
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()][:200]
        except Exception:
            pass
    # Otherwise split by commas or newlines
    terms = [
        term.strip()
        for chunk in stripped.replace("\n", ",").split(",")
        if (term := chunk.strip())
    ]
    return terms[:200]


def _sanitize_filename(name: str | None) -> str:
    """Sanitize uploaded filename for safe storage and downloads."""
    if not name:
        return "document.pdf"
    safe = Path(name).name
    stem = "".join(c for c in Path(safe).stem if c.isalnum() or c in ("-", "_"))[:50]
    return f"{stem or 'document'}.pdf"


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create translation job",
    description=(
        "Accepts a source PDF and translation parameters, creates an in-process "
        "translation job, and launches pipeline execution asynchronously."
    ),
    responses={
        202: {"description": "Job created and queued for processing."},
        400: {"description": "PDF is missing, empty, or corrupted."},
        409: {"description": "Configured provider is not available on server."},
        413: {"description": "PDF exceeds maximum upload size limit."},
        422: {"description": "Invalid mode or language parameters."},
        429: {"description": "Too many concurrent active jobs on server."},
    },
)
async def create_job(
    file: Annotated[UploadFile, File(description="Digital source PDF to translate")],
    target_language: Annotated[
        str, Form(description="Target language code (e.g. 'es')")
    ],
    background_tasks: BackgroundTasks,
    source_language: Annotated[
        str | None, Form(description="Optional source language code")
    ] = None,
    mode: Annotated[
        str, Form(description="Translation mode: 'demo' or 'configured'")
    ] = "demo",
    confirm_configured: Annotated[
        bool, Form(description="Explicit user confirmation for configured translation")
    ] = False,
    protected_terms: Annotated[
        str | None, Form(description="Protected terms list")
    ] = None,
) -> JobCreateResponse:
    """Create a new translation job."""
    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    # 1. Validate target language
    clean_target = (target_language or "").strip().lower()
    if not clean_target:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Target language is required and cannot be empty",
        )
    if clean_target not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported target language '{target_language}'. "
                f"Supported languages: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
            ),
        )

    # 2. Validate source language
    clean_source = (source_language or "").strip().lower()
    if clean_source in ("", "auto", "none"):
        clean_source = None
    elif clean_source not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported source language '{source_language}'. "
                f"Supported languages: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
            ),
        )

    # 3. Validate mode
    clean_mode = (mode or "").strip().lower()
    if clean_mode not in (JobMode.DEMO.value, JobMode.CONFIGURED.value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid translation mode '{mode}'. "
                "Allowed modes: 'demo', 'configured'"
            ),
        )
    job_mode = JobMode(clean_mode)

    # 4. Require explicit backend confirmation for configured mode
    if job_mode == JobMode.CONFIGURED and not confirm_configured:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Configured translation mode requires explicit confirmation "
                "(confirm_configured=true)"
            ),
        )

    # 4. Read PDF file in bounded chunks
    chunks = []
    total_bytes = 0
    while chunk := await file.read(64 * 1024):
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"File exceeds maximum allowed size of "
                    f"{settings.max_upload_size_mb} MB"
                ),
            )
        chunks.append(chunk)

    if total_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF file is empty (0 bytes)",
        )

    pdf_bytes = b"".join(chunks)

    # 5. Verify PDF validity
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        doc.close()
        if page_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded PDF file contains zero pages",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid PDF or is corrupted",
        ) from None

    parsed_terms = _parse_protected_terms(protected_terms)
    safe_filename = _sanitize_filename(file.filename)

    service = get_job_service()
    try:
        job = service.create_job(
            filename=safe_filename,
            source_pdf=pdf_bytes,
            target_language=clean_target,
            source_language=clean_source,
            mode=job_mode,
            protected_terms=parsed_terms,
        )
    except ProviderNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Configured translation provider is not available or "
                "missing required credentials on server"
            ),
        ) from None
    except Exception as e:
        if "Maximum number of active translation jobs reached" in str(e):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Server is currently processing the maximum number of "
                    "concurrent translation jobs. Please retry shortly."
                ),
            ) from None
        logger.error("Failed to create translation job: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error creating translation job",
        ) from None

    background_tasks.add_task(service.run_job, job.job_id)

    return JobCreateResponse(
        job_id=job.job_id,
        status=job.status,
        stage=job.stage,
        stage_message=job.stage_message,
        status_url=f"/api/v1/jobs/{job.job_id}",
        result_url=f"/api/v1/jobs/{job.job_id}/result",
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get translation job status",
    description="Returns metadata and current stage for an active or completed job.",
    responses={
        200: {"description": "Job status metadata returned successfully."},
        404: {"description": "Job not found or has expired from memory."},
    },
)
async def get_job(job_id: str) -> JobResponse:
    """Retrieve safe metadata for a job by UUID."""
    store = get_job_store()
    job = store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation job not found or has expired",
        )
    return JobResponse.model_validate(job)


@router.get(
    "/{job_id}/result",
    summary="Download reconstructed translation result PDF",
    description="Downloads the translated PDF once the job reaches 'completed' status.",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Translated PDF binary stream.",
        },
        400: {"description": "Job failed and has no result available."},
        404: {"description": "Job not found or has expired from memory."},
        409: {"description": "Job is still processing and not yet completed."},
    },
)
async def get_job_result(job_id: str) -> Response:
    """Retrieve and download the translated PDF artifact."""
    store = get_job_store()
    job = store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation job not found or has expired",
        )

    if job.status == JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Translation job failed. Result artifact is not available.",
        )

    if job.status != JobStatus.COMPLETED or not job.result_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Translation job is still in progress (stage: {job.stage})",
        )

    pdf_bytes = store.get_result(job_id)
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Result PDF artifact could not be found in memory",
        )

    stem = (
        "".join(c for c in Path(job.filename).stem if c.isalnum() or c in ("-", "_"))[
            :30
        ]
        or "document"
    )
    download_name = f"tradux-translated-{stem}.pdf"

    headers = {
        "Content-Disposition": f'attachment; filename="{download_name}"',
        "X-Tradux-Job-Id": job.job_id,
        "X-Tradux-Status": job.status.value,
    }
    if job.layout_stats:
        headers["X-Tradux-Fit-Blocks"] = str(job.layout_stats.fit_count)
        headers["X-Tradux-Shrunk-Blocks"] = str(job.layout_stats.shrunk_count)
        headers["X-Tradux-Review-Blocks"] = str(job.layout_stats.review_required_count)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete translation job",
    description="Explicitly deletes a job and frees its memory buffers.",
    responses={
        204: {"description": "Job deleted successfully."},
        404: {"description": "Job not found or has expired from memory."},
        409: {"description": "Cannot delete an active translation job."},
    },
)
async def delete_job(job_id: str) -> Response:
    """Delete a translation job and its memory buffers."""
    store = get_job_store()
    job = store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation job not found or has expired",
        )
    if not job.status.is_terminal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete an active translation job while it is running",
        )
    store.delete(job_id, force=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
