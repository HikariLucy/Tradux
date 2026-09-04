"""Deterministic generator for test PDF documents using pure PyMuPDF."""

from pathlib import Path

import pymupdf


def create_sample_pdf_bytes() -> bytes:
    """Generate deterministic in-memory PDF bytes matching Phase 1 requirements.

    Characteristics:
    - 2 pages (A4 dimensions: 595 x 842 pt);
    - Multiple font sizes: 18pt, 12pt, 9pt;
    - Multiple fonts: Helvetica ('helv'), Times-Roman ('tiro'), Courier ('cour');
    - Color variations: Black (#000000), Red (#FF0000), Blue (#0000FF);
    - Multiple blocks/lines in distinct page positions;
    - Embedded image occurrences sharing a single pixmap to test
      distinct image IDs and bboxes;
    - Metadata: Title and Author.
    """
    doc = pymupdf.open()
    doc.set_metadata(
        {
            "title": "Tradux Sample Document",
            "author": "Tradux Test Suite",
            "subject": "Unit and Integration Testing",
            "keywords": "tradux, testing, layout",
        }
    )

    # Page 1
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text(
        (72, 80),
        "Tradux Test Document - Page 1",
        fontname="helv",
        fontsize=18,
        color=(0, 0, 0),
    )
    p1.insert_text(
        (72, 130),
        "This is the first body paragraph in Times-Roman font.",
        fontname="tiro",
        fontsize=12,
        color=(0, 0, 0),
    )
    p1.insert_text(
        (72, 170),
        "Important notification highlighted in pure red color.",
        fontname="helv",
        fontsize=12,
        color=(1, 0, 0),
    )
    p1.insert_text(
        (72, 780),
        "Page 1 footnote note in Courier font 9pt.",
        fontname="cour",
        fontsize=9,
        color=(0, 0, 1),
    )

    # In-memory pixmap (20x20 RGB)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
    pix.clear_with(220)  # Light gray

    # First occurrence of image
    rect1 = pymupdf.Rect(400, 80, 460, 140)
    p1.insert_image(rect1, pixmap=pix)

    # Second occurrence of same pixmap (tests independent occurrence ID and bbox)
    rect2 = pymupdf.Rect(400, 160, 460, 220)
    p1.insert_image(rect2, pixmap=pix)

    # Page 2
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text(
        (72, 80),
        "Tradux Test Document - Page 2",
        fontname="helv",
        fontsize=16,
        color=(0, 0, 0),
    )
    p2.insert_text(
        (72, 120),
        "Second page body text line number one.",
        fontname="tiro",
        fontsize=11,
        color=(0, 0, 0),
    )
    p2.insert_text(
        (72, 145),
        "Second page body text line number two.",
        fontname="tiro",
        fontsize=11,
        color=(0, 0, 0),
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_sample_pdf_file(target_path: Path) -> Path:
    """Write deterministic sample PDF bytes to a target file."""
    data = create_sample_pdf_bytes()
    target_path.write_bytes(data)
    return target_path


def create_rotated_page_pdf_bytes(rotation: int = 90) -> bytes:
    """Generate a PDF with a rotated page to verify coordinate handling."""
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text(
        (50, 60),
        "Text on Rotated Page",
        fontname="helv",
        fontsize=14,
        color=(0, 0, 0),
    )
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
    page.insert_image(pymupdf.Rect(50, 450, 150, 550), pixmap=pix)
    page.set_rotation(rotation)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_encrypted_pdf_bytes(password: str = "secret") -> bytes:
    """Generate an encrypted password-protected PDF in memory."""
    doc = pymupdf.open()
    p = doc.new_page(width=300, height=300)
    p.insert_text((50, 50), "Secret Protected Text")
    perm = int(pymupdf.PDF_PERM_ACCESSIBILITY)
    pdf_bytes = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw=password,
        permissions=perm,
    )
    doc.close()
    return pdf_bytes


def create_layout_fixture_pdf_bytes() -> bytes:
    """Generate deterministic PDF fixture covering all Phase 3 layout requirements.

    Includes:
    - Colored vector background rectangle with text;
    - Text for simple fit;
    - Text for linguistic expansion;
    - Tiny box for irresolvable overflow / review_required;
    - Embedded image nearby;
    - Untranslated text block;
    - Rotated 90 degree page.
    """
    doc = pymupdf.open()

    # Page 1
    p1 = doc.new_page(width=595, height=842)

    # Colored vector background rectangle
    bg_rect = pymupdf.Rect(50, 40, 545, 100)
    p1.draw_rect(bg_rect, color=(0.8, 0.9, 1.0), fill=(0.8, 0.9, 1.0))
    p1.insert_textbox(
        pymupdf.Rect(60, 50, 535, 90),
        "Text on colored background",
        fontsize=14,
        fontname="helv",
        color=(0.1, 0.2, 0.5),
    )

    # Simple fit source text
    p1.insert_textbox(
        pymupdf.Rect(50, 120, 500, 160),
        "Simple fit source text sentence.",
        fontsize=12,
        fontname="helv",
    )

    # Text to expand
    p1.insert_textbox(
        pymupdf.Rect(50, 180, 500, 230),
        "Short text to expand considerably.",
        fontsize=12,
        fontname="helv",
    )

    # Box for overflow test (tight 30pt height)
    p1.insert_textbox(
        pymupdf.Rect(50, 250, 200, 280),
        "Overflow source text",
        fontsize=10,
        fontname="helv",
    )

    # Image near text
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    pix.clear_with(150)
    p1.insert_image(pymupdf.Rect(50, 300, 110, 360), pixmap=pix)
    p1.insert_textbox(
        pymupdf.Rect(130, 300, 500, 360),
        "Text situated directly next to image.",
        fontsize=12,
        fontname="helv",
    )

    # Untranslated text block (must remain completely untouched)
    p1.insert_textbox(
        pymupdf.Rect(50, 400, 500, 440),
        "Untranslated block that must remain untouched.",
        fontsize=11,
        fontname="cour",
    )

    # Page 2: Rotated 90 degrees
    p2 = doc.new_page(width=400, height=600)
    p2.insert_textbox(
        pymupdf.Rect(50, 50, 350, 120),
        "Rotated page source text block.",
        fontsize=12,
        fontname="helv",
    )
    pix2 = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 30, 30), False)
    pix2.clear_with(200)
    p2.insert_image(pymupdf.Rect(50, 200, 100, 250), pixmap=pix2)
    p2.set_rotation(90)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
