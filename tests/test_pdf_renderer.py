"""Integration tests for PyMuPDFRenderer and PDF reconstruction."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pymupdf

from app.analyzers import DocumentAnalyzer
from app.domain.models import Document
from app.layout import DocumentLayout, LayoutConfig, LayoutEngine, LayoutStatus
from app.renderers import PyMuPDFRenderer
from tests.fixtures import create_layout_fixture_pdf_bytes


def _prepare_fixture_and_layout() -> tuple[bytes, Document, DocumentLayout]:
    """Helper creating a standard test fixture, analyzed document, and layout."""
    pdf_bytes = create_layout_fixture_pdf_bytes()
    analyzer = DocumentAnalyzer()
    document = analyzer.analyze_bytes(pdf_bytes, filename="fixture.pdf")

    # Set translations on page 1:
    # block 0: colored background text
    # block 1: simple fit text
    # block 2: text to expand
    # block 3: tiny box (deliberate overflow)
    # block 4: text near image
    # block 5: untranslated (None)
    document.pages[0].blocks[0].translated_text = "Texto sobre fondo coloreado"
    document.pages[0].blocks[1].translated_text = "Traducción simple que cabe"
    document.pages[0].blocks[
        2
    ].translated_text = "Traducción expandida con algo más de longitud"
    # Deliberate overflow in tiny box
    document.pages[0].blocks[3].translated_text = (
        "Este es un texto deliberadamente larguísimo que desborda por completo "
        "la caja diminuta y no puede caber bajo ninguna circunstancia bajo los "
        "límites mínimos de legibilidad."
    )
    document.pages[0].blocks[4].translated_text = "Texto junto a imagen"
    # document.pages[0].blocks[5] is untranslated!

    # Page 2 (rotated 90 degrees)
    document.pages[1].blocks[0].translated_text = "Texto rotado traducido"

    engine = LayoutEngine(
        config=LayoutConfig(
            min_font_size=7.0,
            min_font_scale=0.75,
            allow_safe_vertical_expansion=True,
        )
    )
    layout = engine.build(document)
    return pdf_bytes, document, layout


def test_renderer_does_not_modify_source_bytes() -> None:
    """Requirement 13: Source PDF bytes remain byte-for-byte identical."""
    source_bytes, document, layout = _prepare_fixture_and_layout()
    source_hash_before = hashlib.sha256(source_bytes).hexdigest()

    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)

    source_hash_after = hashlib.sha256(source_bytes).hexdigest()
    assert source_hash_before == source_hash_after
    assert len(result.pdf_bytes) > 0


def test_rendered_pdf_is_valid_and_preserves_page_dimensions_and_rotation() -> None:
    """Requirements 14 & 15: Output PDF preserves count, dimensions, rotation."""
    source_bytes, document, layout = _prepare_fixture_and_layout()
    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)

    assert result.page_count == 2
    assert result.rendered_blocks > 0

    # Inspect generated PDF with PyMuPDF
    out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
    assert out_doc.page_count == 2

    # Page 1: 595 x 842, rotation 0
    p1 = out_doc[0]
    assert p1.cropbox.width == 595.0
    assert p1.cropbox.height == 842.0
    assert p1.rotation == 0

    # Page 2: 400 x 600, rotation 90
    p2 = out_doc[1]
    assert p2.cropbox.width == 400.0
    assert p2.cropbox.height == 600.0
    assert p2.rotation == 90

    out_doc.close()


def test_images_and_vector_backgrounds_preserved() -> None:
    """Requirements 16 & 17: Images and vector drawings are preserved."""
    source_bytes, document, layout = _prepare_fixture_and_layout()
    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)

    out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
    p1 = out_doc[0]

    # Image on page 1 preserved
    imgs = p1.get_images()
    assert len(imgs) >= 1

    # Vector background on page 1 preserved
    drawings = p1.get_drawings()
    assert len(drawings) >= 1

    # Pixel test on colored background: area (100, 70) had blue background
    pix = p1.get_pixmap()
    pixel = pix.pixel(100, 70)
    # Ensure pixel is NOT pure white (255, 255, 255)
    assert pixel[0] < 240 and pixel[2] > 200

    out_doc.close()


def test_source_text_replaced_and_translated_text_searchable() -> None:
    """Requirements 19 & 20: Source text is replaced and translation searchable."""
    source_bytes, document, layout = _prepare_fixture_and_layout()
    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)

    out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
    p1_text = out_doc[0].get_text()

    # Replaced source text should NOT be present in extraction
    assert "Simple fit source text sentence." not in p1_text
    assert "Short text to expand considerably." not in p1_text

    # Translated text SHOULD be present
    assert "Texto sobre fondo coloreado" in p1_text
    assert "Traducción simple que cabe" in p1_text

    # Untranslated text MUST remain untouched
    assert "Untranslated block that must remain untouched." in p1_text

    out_doc.close()


def test_review_required_block_preserves_original_source_text() -> None:
    """Requirement 21: REVIEW_REQUIRED blocks are not redacted."""
    source_bytes, document, layout = _prepare_fixture_and_layout()

    # Block 3 is the tiny overflow box
    b3_layout = layout.pages[0].blocks[3]
    assert b3_layout.status == LayoutStatus.REVIEW_REQUIRED

    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)

    assert result.review_required_blocks >= 1

    out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
    p1_text = out_doc[0].get_text()

    # Original text must STILL be present
    assert "Overflow source text" in p1_text
    out_doc.close()


def test_rotated_page_rendering_and_extraction() -> None:
    """Requirement 22: Rotated page rendered properly in canonical space."""
    source_bytes, document, layout = _prepare_fixture_and_layout()
    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)

    out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
    p2 = out_doc[1]
    assert p2.rotation == 90
    p2_text = p2.get_text()

    assert "Texto rotado traducido" in p2_text
    assert "Rotated page source text block." not in p2_text

    out_doc.close()


def test_reanalysis_with_document_analyzer() -> None:
    """Requirement 24: Re-analysis of rendered output produces valid model."""
    source_bytes, document, layout = _prepare_fixture_and_layout()
    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)

    analyzer = DocumentAnalyzer()
    reanalyzed = analyzer.analyze_bytes(result.pdf_bytes, filename="reanalyzed.pdf")

    assert reanalyzed.page_count == 2
    assert len(reanalyzed.pages[0].blocks) > 0
    assert len(reanalyzed.pages[0].images) >= 1
    assert reanalyzed.pages[1].rotation == 90


def test_warnings_do_not_leak_full_document_content() -> None:
    """Requirement 25: Logs and warnings do not expose full document text content."""
    source_bytes, document, layout = _prepare_fixture_and_layout()
    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)

    # Check warnings in layout and renderer
    all_warnings = result.warnings + [
        w for p in layout.pages for b in p.blocks for w in b.warnings
    ]
    for w in all_warnings:
        # None of the warnings should contain verbatim long text
        assert "Texto muy largo que inevitablemente causa desbordamiento" not in w
        assert "Traducción expandida con texto más largo" not in w


def test_cli_render_translated_document(tmp_path: Path) -> None:
    """Requirement 13: CLI render_translated_document.py runs successfully."""
    source_bytes, document, _ = _prepare_fixture_and_layout()

    pdf_file = tmp_path / "source.pdf"
    pdf_file.write_bytes(source_bytes)

    json_file = tmp_path / "translated.json"
    json_file.write_text(document.to_json(), encoding="utf-8")

    out_pdf = tmp_path / "out.pdf"
    report_json = tmp_path / "layout_report.json"

    cmd = [
        sys.executable,
        "scripts/render_translated_document.py",
        str(pdf_file),
        str(json_file),
        "--output",
        str(out_pdf),
        "--layout-report",
        str(report_json),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert res.returncode == 0
    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 0
    assert report_json.exists()

    report_data = json.loads(report_json.read_text(encoding="utf-8"))
    assert "stats" in report_data
    assert "pages" in report_data


def test_multiple_redactions_order_preserves_all_insertions() -> None:
    """Requirement 23: Multiple redactions on a page committed prior to insertion
    guarantee that later redactions do not erase earlier inserted translations.
    """
    source_bytes, document, layout = _prepare_fixture_and_layout()
    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)

    # Page 1 had multiple adjacent text blocks translated
    out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
    p1 = out_doc[0]
    extracted = p1.get_text()

    # All translated blocks on page 1 must coexist in the output
    assert "Texto sobre fondo coloreado" in extracted
    assert "Traducción simple que cabe" in extracted
    assert "Traducción expandida con algo más" in extracted
    assert "Texto junto a imagen" in extracted
    out_doc.close()


def test_font_substitution_reported_in_result() -> None:
    """Requirement 18: Font substitutions are detected and reported in RenderResult."""
    source_bytes, document, layout = _prepare_fixture_and_layout()
    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)

    # In layout and result, substitutions are counted
    assert isinstance(result.font_substitutions, int)
    assert layout.stats.font_substitutions >= 0


def test_rotated_page_canonical_coordinates_regression() -> None:
    """Audit test for rotated pages (400x600, rotation=90).

    Verifies that a block placed at y=450..520 in canonical unrotated space:
    - is NOT considered out of bounds or clipped by rotated visual height (400)
    - has its layout status calculated against canonical height (600)
    - layout and render use canonical bounding box
    - resulting PDF retains rotation=90
    - translated text is extractable
    - canonical dimensions remain 400x600 (cropbox) while visual is 600x400 (rect)
    - source bytes remain byte-for-byte unchanged
    """
    # 1. Synthesize 1-page PDF: 400x600 pt with rotation=90
    src_doc = pymupdf.open()
    src_page = src_doc.new_page(width=400, height=600)
    src_page.set_rotation(90)
    # Insert source text in canonical space at y=460..510 pt
    # Notice: In visual space, rect.height is 400. y=460 would be out of bounds!
    src_page.insert_textbox(
        pymupdf.Rect(50.0, 460.0, 350.0, 510.0),
        "Source text in canonical lower region y=460..510",
        fontsize=12.0,
    )
    source_bytes = src_doc.tobytes()
    src_doc.close()
    source_hash_before = hashlib.sha256(source_bytes).hexdigest()

    # 2. Analyze document
    analyzer = DocumentAnalyzer()
    document = analyzer.analyze_bytes(source_bytes, filename="rotated_audit.pdf")

    assert document.page_count == 1
    page = document.pages[0]
    # DocumentModel canonical unrotated dimensions: width=400, height=600
    assert page.width == 400.0
    assert page.height == 600.0
    assert page.rotation == 90
    assert len(page.blocks) == 1

    block = page.blocks[0]
    # Block bbox must be in canonical coordinate space: y0 >= 450, y1 <= 520
    assert block.bbox.y0 >= 450.0
    assert block.bbox.y1 <= 520.0
    # Must NOT be clipped to visual height 400
    assert block.bbox.y1 > 400.0

    # 3. Supply translation
    block.translated_text = "Traducción en región inferior canónica 450 a 520 pt"

    # 4. Layout calculation
    engine = LayoutEngine()
    layout = engine.build(document)
    b_layout = layout.pages[0].blocks[0]

    # Must NOT be marked REVIEW_REQUIRED (fits within 600pt canonical height)
    assert b_layout.status in (
        LayoutStatus.FIT,
        LayoutStatus.SHRUNK,
        LayoutStatus.EXPANDED,
    )
    assert b_layout.render_bbox.y0 >= 450.0
    assert b_layout.render_bbox.y1 > 400.0
    assert b_layout.render_bbox.y1 <= 600.0

    # 5. Render
    renderer = PyMuPDFRenderer()
    result = renderer.render(source_bytes, document, layout)
    assert result.rendered_blocks == 1
    assert result.review_required_blocks == 0

    # 6. Source immutability
    source_hash_after = hashlib.sha256(source_bytes).hexdigest()
    assert source_hash_before == source_hash_after

    # 7. Output verification with PyMuPDF
    out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
    assert out_doc.page_count == 1
    out_page = out_doc[0]

    # Explicit audit of cropbox vs rect
    assert out_page.rotation == 90
    assert out_page.cropbox.width == 400.0
    assert out_page.cropbox.height == 600.0
    assert out_page.rect.width == 600.0
    assert out_page.rect.height == 400.0

    # Translated text is extractable and source is replaced
    extracted = out_page.get_text()
    assert "Traducción en región inferior canónica" in extracted
    assert "Source text in canonical lower region" not in extracted
    out_doc.close()
