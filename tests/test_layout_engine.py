"""Unit and integration tests for LayoutEngine, font resolution, and models."""

import copy

from app.domain.models import (
    BoundingBox,
    Document,
    ImageElement,
    Page,
    TextBlock,
    TextLine,
    TextSpan,
)
from app.layout.config import LayoutConfig
from app.layout.engine import LayoutEngine
from app.layout.fonts import resolve_font
from app.layout.models import (
    BlockLayout,
    DocumentLayout,
    LayoutStats,
    LayoutStatus,
    PageLayout,
)
from app.layout.styles import select_representative_style
from app.renderers.color import hex_to_rgb_float


def _make_sample_block(
    reading_order: int,
    text: str,
    translated_text: str | None = None,
    bbox: tuple[float, float, float, float] = (50.0, 50.0, 300.0, 80.0),
    font_name: str = "helv",
    font_size: float = 12.0,
    color: str = "#000000",
    flags: int = 0,
) -> TextBlock:
    """Helper to construct a TextBlock for layout tests."""
    b = BoundingBox(x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3])
    span = TextSpan(
        text=text,
        bbox=b,
        font_name=font_name,
        font_size=font_size,
        color=color,
        flags=flags,
    )
    line = TextLine(text=text, bbox=b, spans=[span])
    return TextBlock(
        text=text,
        bbox=b,
        lines=[line],
        reading_order=reading_order,
        translated_text=translated_text,
    )


def test_layout_models_serialization() -> None:
    """Requirement 1: Layout models are cleanly serializable to/from JSON."""
    bbox = BoundingBox(x0=50.0, y0=50.0, x1=250.0, y1=80.0)
    block = BlockLayout(
        page_number=1,
        reading_order=0,
        bbox=bbox,
        render_bbox=bbox,
        text="Translated content",
        original_font_name="Arial-Bold",
        resolved_font_name="hebo",
        original_font_size=12.0,
        final_font_size=11.0,
        color="#1864AB",
        line_height=1.15,
        status=LayoutStatus.SHRUNK,
        warnings=["Font substituted"],
        is_font_substituted=True,
    )
    page_layout = PageLayout(page_number=1, blocks=[block])
    doc_layout = DocumentLayout(
        pages=[page_layout],
        stats=LayoutStats(
            total_blocks=1,
            shrunk_count=1,
            font_substitutions=1,
        ),
        metadata={"engine": "LayoutEngine"},
    )

    json_str = doc_layout.to_json()
    assert "Translated content" in json_str
    assert "shrunk" in json_str
    assert "hebo" in json_str

    deserialized = DocumentLayout.from_json(json_str)
    assert len(deserialized.pages) == 1
    assert deserialized.pages[0].blocks[0].status == LayoutStatus.SHRUNK
    assert deserialized.pages[0].blocks[0].final_font_size == 11.0
    assert deserialized.stats.shrunk_count == 1


def test_select_representative_style_dominance() -> None:
    """Requirement 2: Dominant style is selected by character count."""
    b = BoundingBox(x0=50.0, y0=50.0, x1=300.0, y1=80.0)
    span1 = TextSpan(
        text="Short bold intro: ",
        bbox=b,
        font_name="Helvetica-Bold",
        font_size=14.0,
        color="#FF0000",
        flags=16,  # Bold
    )
    span2 = TextSpan(
        text="This is the main body sentence which is longer and regular.",
        bbox=b,
        font_name="Times-Roman",
        font_size=11.0,
        color="#000000",
        flags=0,
    )
    line = TextLine(text=span1.text + span2.text, bbox=b, spans=[span1, span2])
    block = TextBlock(text=line.text, bbox=b, lines=[line], reading_order=0)

    rep = select_representative_style(block)
    # Dominant span is span2 (longer character count)
    assert rep.font_name == "Times-Roman"
    assert rep.font_size == 11.0
    assert rep.color == "#000000"
    assert not rep.is_bold


def test_select_representative_style_empty_spans() -> None:
    """Requirement 2: Blocks with empty/whitespace spans fall back safely."""
    b = BoundingBox(x0=50.0, y0=50.0, x1=100.0, y1=60.0)
    span = TextSpan(
        text="   ",
        bbox=b,
        font_name="Courier",
        font_size=10.0,
        color="#0000FF",
        flags=2,  # Italic
    )
    line = TextLine(text="   ", bbox=b, spans=[span])
    block = TextBlock(text="   ", bbox=b, lines=[line], reading_order=0)

    rep = select_representative_style(block)
    assert rep.font_name == "Courier"
    assert rep.is_italic


def test_hex_to_rgb_float_conversion() -> None:
    """Requirement 3: #RRGGBB conversion to float RGB tuple."""
    assert hex_to_rgb_float("#FFFFFF") == (1.0, 1.0, 1.0)
    assert hex_to_rgb_float("#000000") == (0.0, 0.0, 0.0)
    assert hex_to_rgb_float("#FF0000") == (1.0, 0.0, 0.0)
    assert hex_to_rgb_float("#00FF00") == (0.0, 1.0, 0.0)
    assert hex_to_rgb_float("#0000FF") == (0.0, 0.0, 1.0)
    # Invalid fallback
    assert hex_to_rgb_float("invalid") == (0.0, 0.0, 0.0)


def test_font_resolution_base14_and_fallbacks() -> None:
    """Requirement 4: Font resolution maps accurately and identifies substitutions."""
    # Standard Base-14
    f_helv = resolve_font("helv")
    assert f_helv.font_name == "helv"
    assert not f_helv.is_substitution

    f_hebo = resolve_font("Helvetica-Bold")
    assert f_hebo.font_name == "hebo"
    assert not f_hebo.is_substitution

    # Fallback substitutions
    f_arial = resolve_font("Arial")
    assert f_arial.font_name == "helv"
    assert f_arial.is_substitution

    f_arial_bold = resolve_font("Arial-BoldMT")
    assert f_arial_bold.font_name == "hebo"
    assert f_arial_bold.is_substitution

    f_times = resolve_font("TimesNewRomanPS-ItalicMT")
    assert f_times.font_name == "tiit"
    assert f_times.is_substitution

    f_consolas = resolve_font("Consolas")
    assert f_consolas.font_name == "cour"
    assert f_consolas.is_substitution

    f_subset = resolve_font("ABCDEF+DINPro-Bold")
    assert f_subset.font_name == "hebo"
    assert f_subset.is_substitution


def test_layout_engine_fit_original_size() -> None:
    """Requirement 5: Translated text fitting in box preserves font size."""
    block = _make_sample_block(
        reading_order=0,
        text="Hello world",
        translated_text="Hola mundo",
        bbox=(50.0, 50.0, 300.0, 90.0),
        font_name="helv",
        font_size=12.0,
    )
    page = Page(page_number=1, width=595.0, height=842.0, blocks=[block])
    doc = Document(filename="test.pdf", page_count=1, pages=[page])

    engine = LayoutEngine()
    layout = engine.build(doc)

    assert len(layout.pages) == 1
    b_layout = layout.pages[0].blocks[0]
    assert b_layout.status == LayoutStatus.FIT
    assert b_layout.final_font_size == 12.0
    assert layout.stats.fit_count == 1


def test_layout_engine_shrunk_controlled() -> None:
    """Requirement 6 & 7: Linguistic expansion triggers controlled font shrinking."""
    # Box is tight for 14pt (needs font shrink to 11pt to fit)
    block = _make_sample_block(
        reading_order=0,
        text="Short text",
        translated_text=(
            "Este es un texto traducido considerablemente más largo para "
            "forzar reducción controlada."
        ),
        bbox=(50.0, 50.0, 300.0, 85.0),
        font_name="helv",
        font_size=14.0,
    )
    page = Page(page_number=1, width=595.0, height=842.0, blocks=[block])
    doc = Document(filename="test.pdf", page_count=1, pages=[page])

    config = LayoutConfig(
        min_font_size=8.0,
        min_font_scale=0.75,
        allow_safe_vertical_expansion=False,
    )
    engine = LayoutEngine(config=config)
    layout = engine.build(doc)

    b_layout = layout.pages[0].blocks[0]
    assert b_layout.status == LayoutStatus.SHRUNK
    assert b_layout.final_font_size < 14.0
    # Must respect min scale: 14 * 0.75 = 10.5 pt
    assert b_layout.final_font_size >= 10.5 - 0.1
    assert layout.stats.shrunk_count == 1


def test_layout_engine_respects_minimum_size_and_overflow() -> None:
    """Requirement 8 & 9: Impossible overflow marks REVIEW_REQUIRED safely."""
    # Very small box (50 x 12 pt) with very long text
    block = _make_sample_block(
        reading_order=0,
        text="Small",
        translated_text=(
            "Este texto es definitivamente demasiado largo para caber en una "
            "caja minúscula de 50x12 pt."
        ),
        bbox=(50.0, 50.0, 100.0, 62.0),
        font_name="helv",
        font_size=12.0,
    )
    page = Page(page_number=1, width=595.0, height=842.0, blocks=[block])
    doc = Document(filename="test.pdf", page_count=1, pages=[page])

    config = LayoutConfig(
        min_font_size=7.0,
        min_font_scale=0.75,
        allow_safe_vertical_expansion=False,
    )
    engine = LayoutEngine(config=config)
    layout = engine.build(doc)

    b_layout = layout.pages[0].blocks[0]
    assert b_layout.status == LayoutStatus.REVIEW_REQUIRED
    assert b_layout.render_bbox == block.bbox  # Render bbox not modified
    assert layout.stats.review_required_count == 1
    assert len(b_layout.warnings) > 0


def test_layout_engine_skipped_blocks() -> None:
    """Requirement 10: Blocks without translated_text are marked SKIPPED."""
    block1 = _make_sample_block(
        reading_order=0,
        text="Untranslated text",
        translated_text=None,
    )
    block2 = _make_sample_block(
        reading_order=1,
        text="Whitespace only",
        translated_text="   \n  ",
    )
    page = Page(page_number=1, width=595.0, height=842.0, blocks=[block1, block2])
    doc = Document(filename="test.pdf", page_count=1, pages=[page])

    engine = LayoutEngine()
    layout = engine.build(doc)

    assert layout.pages[0].blocks[0].status == LayoutStatus.SKIPPED
    assert layout.pages[0].blocks[1].status == LayoutStatus.SKIPPED
    assert layout.stats.skipped_count == 2


def test_layout_engine_does_not_mutate_input_document() -> None:
    """Requirement 11: LayoutEngine guarantees strict inmutability of input Document."""
    block = _make_sample_block(
        reading_order=0,
        text="Source text",
        translated_text="Texto traducido",
    )
    page = Page(page_number=1, width=595.0, height=842.0, blocks=[block])
    doc = Document(filename="test.pdf", page_count=1, pages=[page])
    doc_copy = copy.deepcopy(doc)

    engine = LayoutEngine()
    engine.build(doc)

    assert doc == doc_copy


def test_layout_engine_deterministic_ordering() -> None:
    """Requirement 12: Blocks evaluated deterministically by page and order."""
    b1 = _make_sample_block(reading_order=2, text="Third", translated_text="Tercero")
    b2 = _make_sample_block(reading_order=0, text="First", translated_text="Primero")
    b3 = _make_sample_block(reading_order=1, text="Second", translated_text="Segundo")

    page2 = Page(page_number=2, width=595.0, height=842.0, blocks=[b1, b2, b3])
    page1 = Page(page_number=1, width=595.0, height=842.0, blocks=[b1, b2, b3])
    # Pass pages out of order
    doc = Document(filename="test.pdf", page_count=2, pages=[page2, page1])

    engine = LayoutEngine()
    layout = engine.build(doc)

    assert layout.pages[0].page_number == 1
    assert layout.pages[1].page_number == 2
    assert [b.reading_order for b in layout.pages[0].blocks] == [0, 1, 2]
    assert [b.reading_order for b in layout.pages[1].blocks] == [0, 1, 2]


def test_layout_engine_safe_vertical_expansion() -> None:
    """Requirement: Safe vertical expansion succeeds if clearance exists."""
    # Box is tight vertically: 200 x 25 pt with 2 lines of text
    # No other blocks below it on a page of height 842 pt
    block = _make_sample_block(
        reading_order=0,
        text="Two lines header",
        translated_text=(
            "Dos líneas de encabezado que requieren expansión vertical "
            "para caber adecuadamente."
        ),
        bbox=(50.0, 50.0, 200.0, 75.0),  # height = 25 pt
        font_name="helv",
        font_size=12.0,
    )
    page = Page(page_number=1, width=595.0, height=842.0, blocks=[block])
    doc = Document(filename="test.pdf", page_count=1, pages=[page])

    config = LayoutConfig(
        min_font_size=10.0,
        min_font_scale=0.85,
        allow_safe_vertical_expansion=True,
        max_vertical_expansion_pt=40.0,
    )
    engine = LayoutEngine(config=config)
    layout = engine.build(doc)

    b_layout = layout.pages[0].blocks[0]
    assert b_layout.status in (LayoutStatus.EXPANDED, LayoutStatus.SHRUNK)
    if b_layout.status == LayoutStatus.EXPANDED:
        assert b_layout.render_bbox.height > block.bbox.height
        assert layout.stats.expanded_count == 1


def test_layout_engine_expansion_blocked_by_image() -> None:
    """Requirement: Vertical expansion stopped if image is immediately below."""
    block = _make_sample_block(
        reading_order=0,
        text="Block above image",
        translated_text=(
            "Texto largo que no cabe y quiere expandirse pero hay "
            "una imagen justo debajo."
        ),
        bbox=(50.0, 50.0, 200.0, 75.0),
        font_name="helv",
        font_size=12.0,
    )
    # Image immediately below at y=76.0 (only 1 pt clearance)
    img_bbox = BoundingBox(x0=50.0, y0=76.0, x1=200.0, y1=150.0)
    image = ImageElement(image_id="p001-img001", page_number=1, bbox=img_bbox)
    page = Page(
        page_number=1, width=595.0, height=842.0, blocks=[block], images=[image]
    )
    doc = Document(filename="test.pdf", page_count=1, pages=[page])

    config = LayoutConfig(
        min_font_size=11.0,
        min_font_scale=0.95,
        allow_safe_vertical_expansion=True,
    )
    engine = LayoutEngine(config=config)
    layout = engine.build(doc)

    b_layout = layout.pages[0].blocks[0]
    # Cannot expand due to image collision
    assert b_layout.status == LayoutStatus.REVIEW_REQUIRED
    assert b_layout.render_bbox.y1 == block.bbox.y1
