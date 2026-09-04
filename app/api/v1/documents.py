"""API endpoints for document processing and analysis."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.analyzers.document_analyzer import DocumentAnalyzer
from app.core.config import Settings, get_settings
from app.core.errors import (
    DocumentSizeExceededError,
    EmptyDocumentError,
    EncryptedPDFError,
    InvalidPDFError,
    TraduxError,
)
from app.domain.models import Document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/analyze",
    response_model=Document,
    summary="Analyze a digital PDF document",
    description=(
        "Receives a digital PDF file via multipart/form-data and returns "
        "a structured, typed domain Document model containing pages, text blocks, "
        "lines, spans, coordinates, typographic styling, colors, and image inventory."
    ),
    responses={
        200: {"description": "Document parsed and structured successfully."},
        400: {"description": "Invalid file, non-PDF content, or empty document."},
        413: {"description": "Document exceeds maximum upload size limit."},
        422: {"description": "Password-protected or encrypted PDF."},
        500: {"description": "Internal server error during document analysis."},
    },
)
async def analyze_document(
    file: Annotated[UploadFile, File(description="PDF file to analyze")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Document:
    """Analyze a digital PDF file provided via multipart upload."""
    filename = file.filename or "uploaded.pdf"

    # Preliminary validation on filename extension if present
    if file.filename and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Uploaded file '{file.filename}' is not a PDF "
                "(expected .pdf extension)"
            ),
        )

    # Preliminary validation on Content-Type if specified and non-generic
    if file.content_type and file.content_type not in (
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported media type '{file.content_type}'. "
                "Only PDF files are accepted."
            ),
        )

    # Enforce MAX_UPLOAD_SIZE_MB using bounded chunked reading
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    chunk_size = 64 * 1024  # 64 KB
    buffer = bytearray()

    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=(
                        f"File size exceeds maximum permitted limit of "
                        f"{settings.max_upload_size_mb} MB"
                    ),
                )
    finally:
        await file.close()

    if len(buffer) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)",
        )

    analyzer = DocumentAnalyzer()
    try:
        document = analyzer.analyze_bytes(bytes(buffer), filename=filename)
        return document
    except EmptyDocumentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Empty document: {e}",
        ) from e
    except InvalidPDFError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or corrupted PDF file: {e}",
        ) from e
    except EncryptedPDFError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Document is password-protected or encrypted and cannot be processed"
            ),
        ) from e
    except DocumentSizeExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(e),
        ) from e
    except TraduxError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error analyzing document '{filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while analyzing the document",
        ) from e
