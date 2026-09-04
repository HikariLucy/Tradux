"""API endpoints for development Web Workbench."""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.errors import TranslationError
from app.domain.models import Document
from app.translators.engine import TranslationEngine
from app.translators.mock import MockTranslator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workbench", tags=["workbench"])


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
