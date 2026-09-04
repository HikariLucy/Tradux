"""Unit and integration tests for DocumentAnalyzer."""

import hashlib
from pathlib import Path

import pytest

from app.analyzers.document_analyzer import DocumentAnalyzer
from app.core.errors import (
    DocumentNotFoundError,
    EmptyDocumentError,
    EncryptedPDFError,
    InvalidPDFError,
)
from app.domain.models import Document
from tests.fixtures.generator import create_encrypted_pdf_bytes


def test_analyze_valid_file(sample_pdf_file: Path) -> None:
    """Validate analyzing a PDF file from a local filesystem path."""
    analyzer = DocumentAnalyzer()
    doc = analyzer.analyze_file(sample_pdf_file)

    assert isinstance(doc, Document)
    assert doc.filename == sample_pdf_file.name
    assert doc.page_count == 2
    assert len(doc.pages) == 2


def test_analyze_valid_bytes(sample_pdf_bytes: bytes) -> None:
    """Validate analyzing a PDF directly from memory bytes."""
    analyzer = DocumentAnalyzer()
    doc = analyzer.analyze_bytes(sample_pdf_bytes, filename="in_memory.pdf")

    assert isinstance(doc, Document)
    assert doc.filename == "in_memory.pdf"
    assert doc.page_count == 2


def test_page_count_and_dimensions(sample_pdf_file: Path) -> None:
    """Verify page count and precise dimensions in PDF points."""
    analyzer = DocumentAnalyzer()
    doc = analyzer.analyze_file(sample_pdf_file)

    assert doc.page_count == 2
    p1 = doc.pages[0]
    assert p1.page_number == 1
    assert p1.width == pytest.approx(595.0, abs=1.0)
    assert p1.height == pytest.approx(842.0, abs=1.0)
    assert p1.rotation == 0

    p2 = doc.pages[1]
    assert p2.page_number == 2
    assert p2.width == pytest.approx(595.0, abs=1.0)
    assert p2.height == pytest.approx(842.0, abs=1.0)


def test_blocks_lines_and_spans_hierarchy(sample_pdf_bytes: bytes) -> None:
    """Verify hierarchical extraction: Page -> TextBlock -> TextLine -> TextSpan."""
    analyzer = DocumentAnalyzer()
    doc = analyzer.analyze_bytes(sample_pdf_bytes)

    p1 = doc.pages[0]
    assert len(p1.blocks) >= 3

    for block in p1.blocks:
        assert block.bbox.x1 >= block.bbox.x0
        assert block.bbox.y1 >= block.bbox.y0
        assert len(block.lines) >= 1
        assert block.reading_order >= 0
        assert block.block_type == "text"

        for line in block.lines:
            assert line.bbox.x1 >= line.bbox.x0
            assert line.bbox.y1 >= line.bbox.y0
            assert len(line.spans) >= 1
            # Reconstructed line text must match concatenation of span text verbatim
            assert line.text == "".join(s.text for s in line.spans)

        # Reconstructed block text must match newline-joined lines verbatim
        assert block.text == "\n".join(ln.text for ln in block.lines)


def test_verbatim_expected_text(sample_pdf_bytes: bytes) -> None:
    """Verify that expected text content is extracted verbatim without modifications."""
    analyzer = DocumentAnalyzer()
    doc = analyzer.analyze_bytes(sample_pdf_bytes)

    all_text = " ".join(block.text for page in doc.pages for block in page.blocks)

    assert "Tradux Test Document - Page 1" in all_text
    assert "This is the first body paragraph in Times-Roman font." in all_text
    assert "Important notification highlighted in pure red color." in all_text
    assert "Page 1 footnote note in Courier font 9pt." in all_text
    assert "Tradux Test Document - Page 2" in all_text
    assert "Second page body text line number one." in all_text


def test_fonts_and_sizes(sample_pdf_bytes: bytes) -> None:
    """Verify font names and font sizes across spans."""
    analyzer = DocumentAnalyzer()
    doc = analyzer.analyze_bytes(sample_pdf_bytes)

    spans = [
        span
        for page in doc.pages
        for block in page.blocks
        for line in block.lines
        for span in line.spans
    ]

    font_sizes = [round(s.font_size, 1) for s in spans]
    # Check that diverse font sizes were extracted
    assert 18.0 in font_sizes
    assert 12.0 in font_sizes
    assert 9.0 in font_sizes

    # Check font names present
    font_names = [s.font_name.lower() for s in spans]
    assert any("helv" in f for f in font_names)
    assert any("tiro" in f or "times" in f for f in font_names)
    assert any("cour" in f for f in font_names)


def test_color_normalization(sample_pdf_bytes: bytes) -> None:
    """Verify that colors are normalized to uppercase #RRGGBB hex format."""
    analyzer = DocumentAnalyzer()
    doc = analyzer.analyze_bytes(sample_pdf_bytes)

    p1_spans = [
        span
        for block in doc.pages[0].blocks
        for line in block.lines
        for span in line.spans
    ]

    colors = {s.color for s in p1_spans}
    # Black color
    assert "#000000" in colors
    # Non-black colors: pure red and blue
    assert "#FF0000" in colors
    assert "#0000FF" in colors


def test_bounding_box_validity(sample_pdf_bytes: bytes) -> None:
    """Verify that all bounding boxes across all elements satisfy geometry rules."""
    analyzer = DocumentAnalyzer()
    doc = analyzer.analyze_bytes(sample_pdf_bytes)

    for page in doc.pages:
        for block in page.blocks:
            assert block.bbox.x1 >= block.bbox.x0
            assert block.bbox.y1 >= block.bbox.y0
            assert block.bbox.width >= 0
            assert block.bbox.height >= 0

            for line in block.lines:
                assert line.bbox.x1 >= line.bbox.x0
                assert line.bbox.y1 >= line.bbox.y0

                for span in line.spans:
                    assert span.bbox.x1 >= span.bbox.x0
                    assert span.bbox.y1 >= span.bbox.y0


def test_image_inventory_occurrences_and_metadata(sample_pdf_bytes: bytes) -> None:
    """Verify image inventory: deterministic IDs, independent bboxes, and metadata."""
    analyzer = DocumentAnalyzer()
    doc = analyzer.analyze_bytes(sample_pdf_bytes)

    p1_images = doc.pages[0].images
    # Two occurrences of the image on page 1
    assert len(p1_images) == 2

    img1, img2 = p1_images[0], p1_images[1]

    # Deterministic IDs
    assert img1.image_id == "p001-img001"
    assert img2.image_id == "p001-img002"

    # Both occurrences must have valid and distinct bounding boxes
    assert img1.bbox is not None
    assert img2.bbox is not None
    assert img1.bbox.y0 != img2.bbox.y0
    assert img1.bbox.as_tuple() != img2.bbox.as_tuple()

    # Native pixel dimensions
    assert img1.width == 20
    assert img1.height == 20
    assert img2.width == 20
    assert img2.height == 20

    # Format extracted when valid xref exists
    assert img1.format in ("png", "jpeg", None)


def test_determinism_same_bytes_twice(sample_pdf_bytes: bytes) -> None:
    """Verify determinism: analyzing the same bytes twice produces identical models."""
    analyzer = DocumentAnalyzer()
    doc1 = analyzer.analyze_bytes(sample_pdf_bytes, filename="test.pdf")
    doc2 = analyzer.analyze_bytes(sample_pdf_bytes, filename="test.pdf")

    assert doc1 == doc2
    assert doc1.model_dump_json() == doc2.model_dump_json()


def test_rotated_page_handling() -> None:
    """Verify that rotated pages preserve unrotated coordinates and dimensions.

    Validates:
    - rotation == 90;
    - Page.width and Page.height correspond to the unrotated coordinate space;
    - Bboxes before and after applying rotation are identical;
    - Bboxes fit within unrotated dimensions and not within flipped visual dimensions.
    """
    import pymupdf

    # Create unrotated base document (400x600)
    doc_unrot = pymupdf.open()
    page = doc_unrot.new_page(width=400, height=600)
    page.insert_text(
        (50, 60),
        "Text on Rotated Page",
        fontname="helv",
        fontsize=14,
        color=(0, 0, 0),
    )
    # Insert image at y in [450, 550], valid in unrotated 600, invalid in visual 400
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
    page.insert_image(pymupdf.Rect(50, 450, 150, 550), pixmap=pix)
    bytes_unrot = doc_unrot.tobytes()

    # Now rotate the page by 90 degrees
    page.set_rotation(90)
    bytes_rot = doc_unrot.tobytes()
    doc_unrot.close()

    analyzer = DocumentAnalyzer()
    doc_unrot_model = analyzer.analyze_bytes(bytes_unrot, filename="unrotated.pdf")
    doc_rot_model = analyzer.analyze_bytes(bytes_rot, filename="rotated.pdf")

    p_unrot = doc_unrot_model.pages[0]
    p_rot = doc_rot_model.pages[0]

    # 1. Rotation verification
    assert p_unrot.rotation == 0
    assert p_rot.rotation == 90

    # 2. Dimensions correspond strictly to unrotated space (400x600, not 600x400)
    assert p_rot.width == pytest.approx(400.0, abs=0.5)
    assert p_rot.height == pytest.approx(600.0, abs=0.5)
    assert p_rot.width == p_unrot.width
    assert p_rot.height == p_unrot.height

    # 3. Bounding boxes are identical before and after rotation
    assert len(p_rot.blocks) == len(p_unrot.blocks)
    assert len(p_rot.images) == len(p_unrot.images)

    for b_rot, b_unrot in zip(p_rot.blocks, p_unrot.blocks, strict=True):
        assert b_rot.bbox.as_tuple() == pytest.approx(b_unrot.bbox.as_tuple(), abs=0.1)

    for img_rot, img_unrot in zip(p_rot.images, p_unrot.images, strict=True):
        assert img_rot.bbox is not None and img_unrot.bbox is not None
        assert img_rot.bbox.as_tuple() == pytest.approx(
            img_unrot.bbox.as_tuple(), abs=0.1
        )

    # 4. Confirm bbox is validated against unrotated dimensions (height=600):
    # The image at y in [450, 550] sits within 600, but would exceed rotated visual 400
    img_bbox = p_rot.images[0].bbox
    assert img_bbox is not None
    assert 0 <= img_bbox.x0 <= img_bbox.x1 <= p_rot.width
    assert 0 <= img_bbox.y0 <= img_bbox.y1 <= p_rot.height
    assert img_bbox.y1 > 400.0  # Confirms unrotated height space


def test_source_file_immutability(sample_pdf_file: Path) -> None:
    """Verify that analyzing a file leaves the source file strictly unmodified."""
    initial_bytes = sample_pdf_file.read_bytes()
    initial_hash = hashlib.sha256(initial_bytes).hexdigest()

    analyzer = DocumentAnalyzer()
    doc = analyzer.analyze_file(sample_pdf_file)
    assert doc.page_count > 0

    after_bytes = sample_pdf_file.read_bytes()
    after_hash = hashlib.sha256(after_bytes).hexdigest()

    assert initial_hash == after_hash
    assert initial_bytes == after_bytes


def test_nonexistent_file_raises_error() -> None:
    """Verify that analyzing a non-existent file path raises DocumentNotFoundError."""
    analyzer = DocumentAnalyzer()
    with pytest.raises(DocumentNotFoundError, match="Document file not found"):
        analyzer.analyze_file("non_existent_file_path.pdf")


def test_invalid_corrupt_pdf_bytes() -> None:
    """Verify that corrupt non-PDF data raises InvalidPDFError."""
    analyzer = DocumentAnalyzer()
    with pytest.raises(InvalidPDFError, match="Failed to open PDF"):
        analyzer.analyze_bytes(b"This is not a PDF at all.")


def test_empty_bytes_raises_error() -> None:
    """Verify that 0-byte stream raises EmptyDocumentError."""
    analyzer = DocumentAnalyzer()
    with pytest.raises(EmptyDocumentError, match="empty"):
        analyzer.analyze_bytes(b"")


def test_empty_file_raises_error(tmp_path: Path) -> None:
    """Verify that 0-byte file on disk raises EmptyDocumentError."""
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")

    analyzer = DocumentAnalyzer()
    with pytest.raises(EmptyDocumentError, match="empty"):
        analyzer.analyze_file(empty_file)


def test_encrypted_pdf_raises_error() -> None:
    """Verify that password-protected PDF raises EncryptedPDFError."""
    enc_bytes = create_encrypted_pdf_bytes(password="supersecret")
    analyzer = DocumentAnalyzer()
    with pytest.raises(EncryptedPDFError, match="password-protected"):
        analyzer.analyze_bytes(enc_bytes)
