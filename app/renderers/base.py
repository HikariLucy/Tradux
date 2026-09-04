"""Abstract protocol interface for PDF document renderers."""

from pathlib import Path
from typing import BinaryIO, Protocol

from app.domain.models import Document
from app.layout.models import DocumentLayout
from app.renderers.models import RenderResult


class PDFRenderer(Protocol):
    """Protocol contract for rendering a reconstructed PDF from document models."""

    def render(
        self,
        source_pdf: bytes | BinaryIO | str | Path,
        document: Document,
        layout: DocumentLayout,
    ) -> RenderResult:
        """Render a new PDF substituting source text with layout-adjusted translation.

        Args:
            source_pdf: Source PDF as bytes, binary stream, or filesystem path.
            document: Analyzed and translated Document model.
            layout: Calculated DocumentLayout plan.

        Returns:
            RenderResult with raw PDF bytes and execution metrics.
        """
        ...
