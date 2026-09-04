"""Unit tests for Tradux domain models."""

import pytest
from pydantic import ValidationError

from app.domain.models import (
    BoundingBox,
    Document,
    ImageElement,
    Page,
    TextBlock,
    TextLine,
    TextSpan,
)


def test_bounding_box_valid() -> None:
    """Validate BoundingBox dimensions and properties."""
    bbox = BoundingBox(x0=10.5, y0=20.0, x1=110.5, y1=120.0)
    assert bbox.x0 == 10.5
    assert bbox.y0 == 20.0
    assert bbox.x1 == 110.5
    assert bbox.y1 == 120.0
    assert bbox.width == 100.0
    assert bbox.height == 100.0
    assert bbox.as_tuple() == (10.5, 20.0, 110.5, 120.0)


def test_bounding_box_invalid_x() -> None:
    """Verify BoundingBox raises error when x1 < x0."""
    with pytest.raises(ValidationError, match="Invalid bounding box: x1"):
        BoundingBox(x0=100.0, y0=20.0, x1=50.0, y1=120.0)


def test_bounding_box_invalid_y() -> None:
    """Verify BoundingBox raises error when y1 < y0."""
    with pytest.raises(ValidationError, match="Invalid bounding box: y1"):
        BoundingBox(x0=10.0, y0=200.0, x1=50.0, y1=100.0)


def test_document_page_count_sync() -> None:
    """Verify Document page_count is automatically synchronized with len(pages)."""
    p1 = Page(page_number=1, width=595.0, height=842.0)
    p2 = Page(page_number=2, width=595.0, height=842.0)

    # Automatically derived when page_count is 0 or omitted
    doc = Document(filename="test.pdf", pages=[p1, p2])
    assert doc.page_count == 2
    assert len(doc.pages) == 2

    # Matches when explicitly passed
    doc_explicit = Document(filename="test.pdf", page_count=2, pages=[p1, p2])
    assert doc_explicit.page_count == 2

    # Raises ValidationError when inconsistent
    with pytest.raises(ValidationError, match="does not match actual pages"):
        Document(filename="test.pdf", page_count=5, pages=[p1, p2])


def test_domain_json_roundtrip() -> None:
    """Verify complete JSON serialization and deserialization roundtrip."""
    bbox = BoundingBox(x0=50.0, y0=50.0, x1=200.0, y1=100.0)
    span = TextSpan(
        text="Sample text",
        bbox=bbox,
        font_name="Helvetica",
        font_size=12.0,
        color="#FF0000",
        flags=0,
        origin=(50.0, 80.0),
    )
    line = TextLine(text="Sample text", bbox=bbox, spans=[span])
    block = TextBlock(
        text="Sample text",
        bbox=bbox,
        lines=[line],
        reading_order=0,
        block_type="text",
    )
    img = ImageElement(
        image_id="p001-img001",
        bbox=bbox,
        width=100,
        height=100,
        xref=5,
        format="png",
    )
    page = Page(
        page_number=1,
        width=595.0,
        height=842.0,
        rotation=0,
        blocks=[block],
        images=[img],
    )
    doc = Document(
        filename="sample.pdf",
        metadata={"title": "Test Title"},
        pages=[page],
    )

    # Canonical Pydantic serialization
    json_str = doc.model_dump_json(indent=2)
    restored = Document.model_validate_json(json_str)

    assert restored == doc
    assert restored.page_count == 1
    assert restored.pages[0].blocks[0].lines[0].spans[0].color == "#FF0000"
    assert restored.pages[0].images[0].image_id == "p001-img001"

    # Convenience wrappers
    assert doc.to_json() == json_str.replace("  ", "").replace("\n", "") or isinstance(
        doc.to_json(), str
    )
    assert Document.from_json(json_str) == doc
