"""Document analyzer based on PyMuPDF for extracting structured domain models."""

from pathlib import Path
from typing import BinaryIO

import pymupdf

from app.analyzers.color import normalize_color_to_hex
from app.core.errors import (
    DocumentNotFoundError,
    EmptyDocumentError,
    EncryptedPDFError,
    InvalidPDFError,
)
from app.domain.models import (
    BoundingBox,
    Document,
    ImageElement,
    Page,
    TextBlock,
    TextLine,
    TextSpan,
)


def make_bounding_box(x0: float, y0: float, x1: float, y1: float) -> BoundingBox:
    """Create a BoundingBox preserving verbatim coordinates from source."""
    return BoundingBox(
        x0=float(x0),
        y0=float(y0),
        x1=float(x1),
        y1=float(y1),
    )


class DocumentAnalyzer:
    """Extracts structured Document domain models from digital PDF files."""

    def analyze_file(self, file_path: str | Path) -> Document:
        """Analyze a PDF from a local filesystem path.

        Guarantees that the input file is opened read-only and never modified.

        Args:
            file_path: Path to the target PDF file.

        Returns:
            Structured Document domain model.

        Raises:
            DocumentNotFoundError: If the file does not exist or is not a file.
            EmptyDocumentError: If the file is 0 bytes or contains no pages.
            InvalidPDFError: If the file is corrupted or not a valid PDF.
            EncryptedPDFError: If the PDF requires a password.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise DocumentNotFoundError(f"Document file not found: {file_path}")
        if not path.is_file():
            raise DocumentNotFoundError(f"Path is not a regular file: {file_path}")

        try:
            if path.stat().st_size == 0:
                raise EmptyDocumentError(
                    f"Document file is empty (0 bytes): {file_path}"
                )
        except OSError as e:
            raise DocumentNotFoundError(f"Error accessing file {file_path}: {e}") from e

        try:
            doc = pymupdf.open(str(path))
        except (pymupdf.FileDataError, pymupdf.EmptyFileError) as e:
            raise InvalidPDFError(f"Failed to open PDF file: {e}") from e
        except Exception as e:
            raise InvalidPDFError(f"Unexpected error opening PDF: {e}") from e

        return self._extract_document(doc, filename=path.name)

    def analyze_bytes(
        self,
        pdf_bytes: bytes | BinaryIO,
        filename: str | None = None,
    ) -> Document:
        """Analyze a PDF directly from memory bytes or a binary stream.

        Args:
            pdf_bytes: PDF content as bytes or a binary file-like stream.
            filename: Optional logical name for the document.

        Returns:
            Structured Document domain model.

        Raises:
            EmptyDocumentError: If bytes are empty or document contains no pages.
            InvalidPDFError: If content is corrupted or not a valid PDF.
            EncryptedPDFError: If the PDF requires a password.
        """
        if hasattr(pdf_bytes, "read"):
            data = pdf_bytes.read()
        else:
            data = pdf_bytes

        if not data or len(data) == 0:
            raise EmptyDocumentError("Document stream is empty (0 bytes)")

        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except (pymupdf.FileDataError, pymupdf.EmptyFileError) as e:
            raise InvalidPDFError(f"Failed to open PDF from bytes: {e}") from e
        except Exception as e:
            raise InvalidPDFError(f"Unexpected error parsing PDF stream: {e}") from e

        return self._extract_document(doc, filename=filename)

    def _extract_document(
        self,
        doc: pymupdf.Document,
        filename: str | None = None,
    ) -> Document:
        """Extract structured document hierarchy from an open PyMuPDF document."""
        try:
            if doc.is_encrypted and doc.needs_pass != 0:
                raise EncryptedPDFError(
                    "PDF document is password-protected or encrypted "
                    "and cannot be opened"
                )

            if doc.page_count == 0:
                raise EmptyDocumentError("PDF document contains zero pages")

            # Extract clean metadata dictionary
            metadata: dict[str, str] = {}
            if doc.metadata:
                for k, v in doc.metadata.items():
                    if v is not None and isinstance(v, (str, int, float, bool)):
                        metadata[str(k)] = str(v)

            pages: list[Page] = []
            for page_idx in range(doc.page_count):
                page = doc.load_page(page_idx)
                # 1-indexed page number for domain representation
                page_number = page_idx + 1

                extracted_page = self._extract_page(doc, page, page_number)
                pages.append(extracted_page)

            return Document(
                filename=filename,
                page_count=len(pages),
                metadata=metadata,
                pages=pages,
            )
        finally:
            doc.close()

    def _extract_page(
        self,
        doc: pymupdf.Document,
        page: pymupdf.Page,
        page_number: int,
    ) -> Page:
        """Extract a single page's text blocks and image elements."""
        # Unrotated page dimensions consistent with unrotated bounding boxes
        cropbox = page.cropbox
        width = float(cropbox.width)
        height = float(cropbox.height)
        rotation = int(page.rotation)

        # 1. Extract text hierarchy via page.get_text("dict")
        page_dict = page.get_text("dict")
        blocks_data = page_dict.get("blocks", [])

        extracted_blocks: list[TextBlock] = []
        reading_order_idx = 0

        for raw_block in blocks_data:
            block_type_num = raw_block.get("type", 0)
            # Only process text blocks (type 0)
            if block_type_num != 0:
                continue

            block_bbox_raw = raw_block.get("bbox", (0, 0, 0, 0))
            block_bbox = make_bounding_box(*block_bbox_raw)

            extracted_lines: list[TextLine] = []
            for raw_line in raw_block.get("lines", []):
                line_bbox_raw = raw_line.get("bbox", (0, 0, 0, 0))
                line_bbox = make_bounding_box(*line_bbox_raw)

                extracted_spans: list[TextSpan] = []
                for raw_span in raw_line.get("spans", []):
                    span_bbox_raw = raw_span.get("bbox", (0, 0, 0, 0))
                    span_bbox = make_bounding_box(*span_bbox_raw)

                    origin_val = raw_span.get("origin")
                    origin_tuple: tuple[float, float] | None = None
                    if origin_val and len(origin_val) >= 2:
                        origin_tuple = (float(origin_val[0]), float(origin_val[1]))

                    span = TextSpan(
                        text=str(raw_span.get("text", "")),
                        bbox=span_bbox,
                        font_name=str(raw_span.get("font", "")),
                        font_size=float(raw_span.get("size", 0.0)),
                        color=normalize_color_to_hex(raw_span.get("color")),
                        flags=int(raw_span.get("flags", 0)),
                        origin=origin_tuple,
                    )
                    extracted_spans.append(span)

                # Reconstruct line text from spans preserving exact sequence
                line_text = "".join(s.text for s in extracted_spans)
                line = TextLine(
                    text=line_text,
                    bbox=line_bbox,
                    spans=extracted_spans,
                )
                extracted_lines.append(line)

            # Verbatim reconstruction of block text joining lines with newline
            block_text = "\n".join(ln.text for ln in extracted_lines)
            block = TextBlock(
                text=block_text,
                bbox=block_bbox,
                lines=extracted_lines,
                reading_order=reading_order_idx,
                block_type="text",
            )
            extracted_blocks.append(block)
            reading_order_idx += 1

        # 2. Extract image occurrences via page.get_image_info(xrefs=True)
        # Each occurrence on the page gets an independent ImageElement with its own bbox
        extracted_images: list[ImageElement] = []
        try:
            image_infos = page.get_image_info(xrefs=True)
        except Exception:
            image_infos = []

        for img_idx, img_info in enumerate(image_infos, start=1):
            image_id = f"p{page_number:03d}-img{img_idx:03d}"

            img_bbox_raw = img_info.get("bbox")
            img_bbox: BoundingBox | None = None
            if img_bbox_raw and len(img_bbox_raw) >= 4:
                img_bbox = make_bounding_box(*img_bbox_raw)

            width_val = img_info.get("width")
            native_width = int(width_val) if width_val is not None else None

            height_val = img_info.get("height")
            native_height = int(height_val) if height_val is not None else None

            raw_xref = img_info.get("xref")
            valid_xref = int(raw_xref) if raw_xref and raw_xref > 0 else None

            # Only call extract_image if valid_xref exists and is > 0
            img_format: str | None = None
            if valid_xref is not None:
                try:
                    img_dict = doc.extract_image(valid_xref)
                    if img_dict and "ext" in img_dict:
                        img_format = str(img_dict["ext"]).lower()
                except Exception:
                    img_format = None

            image_element = ImageElement(
                image_id=image_id,
                bbox=img_bbox,
                width=native_width,
                height=native_height,
                xref=valid_xref,
                format=img_format,
            )
            extracted_images.append(image_element)

        return Page(
            page_number=page_number,
            width=width,
            height=height,
            rotation=rotation,
            blocks=extracted_blocks,
            images=extracted_images,
        )
