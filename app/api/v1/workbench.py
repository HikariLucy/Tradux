"""API endpoints for development Web Workbench."""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.errors import TranslationError
from app.domain.models import Document
from app.layout import LayoutEngine
from app.renderers import PyMuPDFRenderer
from app.translators.engine import TranslationEngine
from app.translators.mock import MockTranslator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workbench", tags=["workbench"])

MAX_DOCUMENT_JSON_SIZE_BYTES: int = 30 * 1024 * 1024


class WorkbenchTranslateRequest(BaseModel):
    """Request payload for workbench mock translation."""

    document: Document = Field(
        ...,
        description="Structured Document domain model to translate",
    )
    source_language: str | None = Field(
        default=None,
        description="Optional source language code (None = auto-detect)",
    )
    target_language: str = Field(
        default="es",
        description="Target language code (e.g. 'es', 'fr', 'en')",
    )
    protected_terms: list[str] = Field(
        default_factory=list,
        description="List of verbatim terms that must not be translated",
    )


class WorkbenchTranslateResponse(BaseModel):
    """Response payload for workbench mock translation."""

    mode: str = Field(
        default="mock",
        description="Translation provider mode (always 'mock' for local workbench)",
    )
    translated_blocks: int = Field(
        ...,
        description="Total number of text blocks that received translated text",
    )
    document: Document = Field(
        ...,
        description="Deep-cloned Document model with translated_text populated",
    )


@router.post(
    "/translate",
    response_model=WorkbenchTranslateResponse,
    summary="Development Workbench preview translation",
    description=(
        "Translates a Document model for the local Workbench preview without external "
        "network calls or API keys, strictly forcing MockTranslator. This endpoint is "
        "a development tool for inspecting the translation pipeline and does not "
        "produce final rendered PDFs."
    ),
    responses={
        200: {
            "description": (
                "Document preview translated successfully with MockTranslator."
            )
        },
        422: {"description": "Invalid document model payload or integrity violation."},
        500: {"description": "Internal server error during preview translation."},
    },
)
async def workbench_translate(
    request: WorkbenchTranslateRequest,
) -> WorkbenchTranslateResponse:
    """Execute mock translation on the Document model for workbench inspection."""
    try:
        # Strictly force MockTranslator: zero network, zero cost, deterministic
        engine = TranslationEngine(translator=MockTranslator())
        translated_doc = await engine.translate_document(
            document=request.document,
            source_language=request.source_language,
            target_language=request.target_language,
            protected_terms=request.protected_terms,
        )
    except TranslationError as e:
        logger.warning(
            "Workbench translation integrity error at page=%s, block=%s: %s",
            e.page_number,
            e.reading_order,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Translation error: {type(e).__name__}",
        ) from None
    except Exception:
        logger.exception("Unexpected error during workbench translation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error during workbench translation",
        ) from None

    translated_count = sum(
        1
        for page in translated_doc.pages
        for block in page.blocks
        if block.translated_text is not None
    )

    return WorkbenchTranslateResponse(
        mode="mock",
        translated_blocks=translated_count,
        document=translated_doc,
    )


@router.post(
    "/render",
    summary="Development Workbench preview PDF reconstruction",
    description=(
        "Reconstructs and downloads a digital PDF from the source PDF and translated "
        "Document model JSON using LayoutEngine and PyMuPDFRenderer. "
        "Strictly runs offline in memory."
    ),
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": (
                "Reconstructed demo PDF returned as a downloadable binary stream."
            ),
        },
        400: {"description": "Empty, missing, or invalid file uploaded."},
        413: {"description": "Uploaded file exceeds maximum allowed size."},
        415: {"description": "Unsupported media type for document JSON."},
        422: {"description": "Invalid Document model JSON payload."},
        500: {
            "description": "Internal error during layout calculation or PDF rendering."
        },
    },
)
async def workbench_render(
    document: Annotated[
        UploadFile,
        File(description="Translated Document model JSON file (application/json)"),
    ],
    file: Annotated[
        UploadFile | None,
        File(description="Original digital source PDF"),
    ] = None,
    source_pdf: Annotated[
        UploadFile | None,
        File(description="Original digital source PDF (alias)"),
    ] = None,
) -> Response:
    """Render and download a reconstructed demonstration PDF."""
    settings = get_settings()
    max_pdf_bytes = settings.max_upload_size_mb * 1024 * 1024
    max_json_bytes = MAX_DOCUMENT_JSON_SIZE_BYTES

    # 1. Validate PDF file presence
    pdf_upload = file or source_pdf
    if pdf_upload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source PDF file is required (field 'file' or 'source_pdf')",
        )

    # 2. Validate Document Content-Type if provided
    if document.content_type and document.content_type not in (
        "application/json",
        "text/json",
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Invalid Content-Type '{document.content_type}' for document JSON "
                "(expected application/json)"
            ),
        )

    # 3. Read Document JSON in bounded chunks
    json_chunks = []
    total_json_bytes = 0
    while chunk := await document.read(64 * 1024):
        total_json_bytes += len(chunk)
        if total_json_bytes > max_json_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Document JSON exceeds maximum allowed size of "
                    f"{max_json_bytes // (1024 * 1024)} MB"
                ),
            )
        json_chunks.append(chunk)

    if total_json_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document JSON file is empty (0 bytes)",
        )

    raw_json = b"".join(json_chunks)
    try:
        json_str = raw_json.decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document JSON file is not valid UTF-8: {e}",
        ) from None

    try:
        document_model = Document.model_validate_json(json_str)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid Document model JSON payload: {e}",
        ) from None

    # 4. Read Source PDF in bounded chunks
    pdf_chunks = []
    total_pdf_bytes = 0
    while chunk := await pdf_upload.read(64 * 1024):
        total_pdf_bytes += len(chunk)
        if total_pdf_bytes > max_pdf_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"File exceeds maximum allowed size of "
                    f"{settings.max_upload_size_mb} MB"
                ),
            )
        pdf_chunks.append(chunk)

    pdf_bytes = b"".join(pdf_chunks)
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded source PDF file is empty (0 bytes)",
        )

    # 5. Execute Layout & Render
    try:
        engine = LayoutEngine()
        layout = engine.build(document_model)
        renderer = PyMuPDFRenderer()
        result = renderer.render(
            source_pdf=pdf_bytes,
            document=document_model,
            layout=layout,
        )
    except Exception as e:
        logger.exception("Error rendering PDF in workbench")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rendering PDF: {e}",
        ) from None

    safe_name = Path(pdf_upload.filename or "document").stem
    clean_stem = (
        "".join(c for c in safe_name if c.isalnum() or c in ("-", "_"))[:30] or "demo"
    )
    download_name = f"tradux-preview-{clean_stem}.pdf"

    headers = {
        "Content-Disposition": f'attachment; filename="{download_name}"',
        "X-Tradux-Rendered-Blocks": str(result.rendered_blocks),
        "X-Tradux-Fit-Blocks": str(layout.stats.fit_count),
        "X-Tradux-Shrunk-Blocks": str(layout.stats.shrunk_count),
        "X-Tradux-Review-Blocks": str(result.review_required_blocks),
    }

    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )
