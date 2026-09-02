"""Test PyMuPDF installation and in-memory operations."""

import pymupdf


def test_pymupdf_in_memory_doc() -> None:
    """Validate that PyMuPDF can create, populate, and read a PDF in memory."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4 dimensions in points
    text = "Tradux Bootstrap Test"
    page.insert_text(pymupdf.Point(50, 50), text, fontsize=12)

    extracted_text = page.get_text()
    assert text in extracted_text

    # Verify document bytes can be written to memory
    pdf_bytes = doc.tobytes()
    assert len(pdf_bytes) > 0

    # Verify reopening from memory bytes
    reopened = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert reopened.page_count == 1
    assert text in reopened[0].get_text()

    doc.close()
    reopened.close()
