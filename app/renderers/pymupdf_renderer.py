"""PyMuPDF-based PDF renderer implementing text redaction and replacement."""

from pathlib import Path
from typing import BinaryIO

import pymupdf

from app.core.errors import InvalidPDFError
from app.domain.models import Document
from app.layout.models import DocumentLayout, LayoutStatus
from app.renderers.base import PDFRenderer
from app.renderers.color import hex_to_rgb_float
from app.renderers.models import RenderResult


class PyMuPDFRenderer(PDFRenderer):
    """Reconstructs translated PDF documents using PyMuPDF.

    Operates strictly on in-memory copies of the source PDF, preserving original
    page geometry, rotations, embedded images, and vector graphics.
    """

    def render(
        self,
        source_pdf: bytes | BinaryIO | str | Path,
        document: Document,
        layout: DocumentLayout,
    ) -> RenderResult:
        """Render a reconstructed PDF from a source PDF and calculated layout plan.

        Args:
            source_pdf: Source PDF bytes, binary stream, or file path.
            document: Document model corresponding to the source.
            layout: Calculated DocumentLayout with per-block rendering instructions.

        Returns:
            RenderResult containing newly generated PDF bytes and execution metrics.

        Raises:
            InvalidPDFError: If source PDF cannot be opened or page counts mismatch.
        """
        pdf_bytes = self._read_source_bytes(source_pdf)

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise InvalidPDFError(
                f"Failed to open source PDF for rendering: {e}"
            ) from e

        try:
            return self._render_document(doc, layout)
        finally:
            if not doc.is_closed:
                doc.close()

    def _read_source_bytes(self, source_pdf: bytes | BinaryIO | str | Path) -> bytes:
        """Read source input into an immutable bytes object."""
        if isinstance(source_pdf, (str, Path)):
            path = Path(source_pdf)
            if not path.is_file():
                raise InvalidPDFError(f"Source PDF file not found: {source_pdf}")
            return path.read_bytes()
        elif hasattr(source_pdf, "read"):
            data = source_pdf.read()
            if isinstance(data, str):
                return data.encode("utf-8")
            return bytes(data)
        return bytes(source_pdf)

    def _render_document(
        self,
        doc: pymupdf.Document,
        layout: DocumentLayout,
    ) -> RenderResult:
        """Execute page-by-page redactions and text insertions."""
        total_pages = doc.page_count
        layout_page_count = len(layout.pages)
        if total_pages != layout_page_count:
            raise InvalidPDFError(
                f"Page count mismatch between source PDF ({total_pages}) "
                f"and layout plan ({layout_page_count})"
            )

        rendered_blocks_count = 0
        skipped_blocks_count = 0
        review_required_blocks_count = 0
        font_substitutions_count = 0
        warnings: list[str] = []

        # Process page by page
        for page_idx in range(total_pages):
            page = doc.load_page(page_idx)
            page_layout = layout.pages[page_idx]

            # 1. Categorize blocks
            renderable_blocks = []
            for block_layout in page_layout.blocks:
                if block_layout.status in (
                    LayoutStatus.FIT,
                    LayoutStatus.SHRUNK,
                    LayoutStatus.EXPANDED,
                ):
                    renderable_blocks.append(block_layout)
                elif block_layout.status == LayoutStatus.REVIEW_REQUIRED:
                    # Do NOT redact review-required blocks; preserve original text
                    review_required_blocks_count += 1
                    warnings.append(
                        f"Page {page_layout.page_number} "
                        f"block {block_layout.reading_order} "
                        "retained original text (review required / overflow)"
                    )
                elif block_layout.status == LayoutStatus.SKIPPED:
                    skipped_blocks_count += 1

            if not renderable_blocks:
                continue

            # 2. Stage A: Apply ALL redactions for this page first
            for b in renderable_blocks:
                # Redact exactly the source text's canonical bounding box
                r = pymupdf.Rect(b.bbox.x0, b.bbox.y0, b.bbox.x1, b.bbox.y1)
                # fill=None avoids white fill, preserving vector backgrounds
                page.add_redact_annot(r, fill=None)

            # 3. Stage B: Commit redactions once with explicit preservation flags
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_NONE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                text=pymupdf.PDF_REDACT_TEXT_REMOVE,
            )

            # 4. Stage C: Insert all translated texts into their render bounding boxes
            for b in renderable_blocks:
                r_render = pymupdf.Rect(
                    b.render_bbox.x0,
                    b.render_bbox.y0,
                    b.render_bbox.x1,
                    b.render_bbox.y1,
                )
                text_color = hex_to_rgb_float(b.color)

                rc = page.insert_textbox(
                    r_render,
                    b.text,
                    fontname=b.resolved_font_name,
                    fontsize=b.final_font_size,
                    color=text_color,
                    lineheight=b.line_height,
                )

                if rc < 0:
                    # Insertion deficit detected at render time
                    warnings.append(
                        f"Page {page_layout.page_number} block {b.reading_order} "
                        f"had unexpected render insertion deficit ({rc:.2f}pt)"
                    )

                rendered_blocks_count += 1
                if b.is_font_substituted:
                    font_substitutions_count += 1

        # Deflate and clean up unused objects to produce standard compact PDF
        rendered_bytes = doc.tobytes(garbage=3, deflate=True)

        return RenderResult(
            pdf_bytes=rendered_bytes,
            page_count=total_pages,
            rendered_blocks=rendered_blocks_count,
            skipped_blocks=skipped_blocks_count,
            review_required_blocks=review_required_blocks_count,
            font_substitutions=font_substitutions_count,
            warnings=warnings,
        )
