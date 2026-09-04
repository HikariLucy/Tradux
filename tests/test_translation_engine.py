"""Unit tests for TranslationEngine and translation workflows."""

import pytest

from app.analyzers.document_analyzer import DocumentAnalyzer
from app.core.errors import TranslationIntegrityError, TranslationProviderError
from app.domain.models import (
    BoundingBox,
    Document,
    ImageElement,
    Page,
    TextBlock,
    TextLine,
    TextSpan,
)
from app.translators.base import Translator
from app.translators.engine import TranslationEngine
from app.translators.mock import MockTranslator
from app.translators.models import TranslationRequest, TranslationResult


def _create_minimal_document() -> Document:
    """Create a minimal 2-page Document model for testing."""
    bbox1 = BoundingBox(x0=50.0, y0=50.0, x1=200.0, y1=70.0)
    span1 = TextSpan(
        text="First heading",
        bbox=bbox1,
        font_name="Helvetica-Bold",
        font_size=14.0,
        color="#000000",
        flags=0,
    )
    line1 = TextLine(text="First heading", bbox=bbox1, spans=[span1])
    b0 = TextBlock(
        bbox=bbox1,
        text="First heading",
        lines=[line1],
        reading_order=0,
    )

    bbox_empty = BoundingBox(x0=50.0, y0=80.0, x1=400.0, y1=100.0)
    span_empty = TextSpan(
        text="   ",
        bbox=bbox_empty,
        font_name="Helvetica",
        font_size=10.0,
        color="#323232",
        flags=0,
    )
    line_empty = TextLine(text="   ", bbox=bbox_empty, spans=[span_empty])
    b1 = TextBlock(
        bbox=bbox_empty,
        text="   ",
        lines=[line_empty],
        reading_order=1,
    )

    bbox2 = BoundingBox(x0=50.0, y0=110.0, x1=400.0, y1=130.0)
    span2 = TextSpan(
        text="Body paragraph on page 1 with TRADUX-PRO.",
        bbox=bbox2,
        font_name="Helvetica",
        font_size=10.0,
        color="#323232",
        flags=0,
    )
    line2 = TextLine(
        text="Body paragraph on page 1 with TRADUX-PRO.", bbox=bbox2, spans=[span2]
    )
    b2 = TextBlock(
        bbox=bbox2,
        text="Body paragraph on page 1 with TRADUX-PRO.",
        lines=[line2],
        reading_order=2,
    )

    img = ImageElement(
        image_id="p001-img001",
        bbox=BoundingBox(x0=50.0, y0=200.0, x1=250.0, y1=350.0),
        width=200,
        height=150,
        format="png",
    )

    p1 = Page(
        page_number=1,
        width=612.0,
        height=792.0,
        rotation=0,
        blocks=[b0, b1, b2],
        images=[img],
    )

    bbox3 = BoundingBox(x0=60.0, y0=60.0, x1=300.0, y1=80.0)
    span3 = TextSpan(
        text="Page 2 text block.",
        bbox=bbox3,
        font_name="Helvetica",
        font_size=11.0,
        color="#000000",
        flags=0,
    )
    line3 = TextLine(text="Page 2 text block.", bbox=bbox3, spans=[span3])
    b3 = TextBlock(
        bbox=bbox3,
        text="Page 2 text block.",
        lines=[line3],
        reading_order=0,
    )

    p2 = Page(
        page_number=2,
        width=612.0,
        height=792.0,
        rotation=90,
        blocks=[b3],
        images=[],
    )

    return Document(
        filename="test.pdf",
        page_count=2,
        pages=[p1, p2],
    )


def test_text_block_translated_text_backwards_compatible_and_roundtrip() -> None:
    """Verify translated_text is optional and roundtrips through JSON without loss."""
    # 1. Default is None (backwards compatible with Phase 1)
    bbox = BoundingBox(x0=10.0, y0=10.0, x1=50.0, y1=20.0)
    block = TextBlock(
        bbox=bbox,
        text="Hello",
        reading_order=0,
    )
    assert block.translated_text is None

    # 2. Can be populated and serialized
    block.translated_text = "Hola"
    json_data = block.model_dump_json()
    assert '"translated_text":"Hola"' in json_data

    # 3. Deserializes with translated_text preserved
    restored = TextBlock.model_validate_json(json_data)
    assert restored.translated_text == "Hola"

    # 4. Phase 1 JSON without translated_text field parses cleanly with None
    phase1_json = (
        '{"bbox":{"x0":10.0,"y0":10.0,"x1":50.0,"y1":20.0},'
        '"text":"Hello","reading_order":0}'
    )
    from_phase1 = TextBlock.model_validate_json(phase1_json)
    assert from_phase1.translated_text is None


@pytest.mark.asyncio
async def test_translation_engine_immutability() -> None:
    """Verify source Document is strictly not mutated during translation."""
    doc = _create_minimal_document()
    engine = TranslationEngine(MockTranslator())

    translated = await engine.translate_document(
        doc, target_language="es", protected_terms=["TRADUX-PRO"]
    )

    # Returned document is a separate object
    assert translated is not doc
    assert translated.pages[0] is not doc.pages[0]

    # Source document blocks must STILL have translated_text as None
    for page in doc.pages:
        for block in page.blocks:
            assert block.translated_text is None

    # Translated document blocks have translated_text populated
    p1_b0 = translated.pages[0].blocks[0]
    assert p1_b0.translated_text is not None
    assert p1_b0.translated_text.startswith("[ES] ")


@pytest.mark.asyncio
async def test_translation_engine_preserves_geometry_and_styling() -> None:
    """Verify all bounding boxes, fonts, colors, images, and rotations are preserved."""
    doc = _create_minimal_document()
    engine = TranslationEngine(MockTranslator())

    translated = await engine.translate_document(doc, target_language="es")

    assert translated.page_count == doc.page_count
    for orig_page, trans_page in zip(doc.pages, translated.pages, strict=True):
        assert trans_page.page_number == orig_page.page_number
        assert trans_page.width == orig_page.width
        assert trans_page.height == orig_page.height
        assert trans_page.rotation == orig_page.rotation

        # Check images preservation
        assert len(trans_page.images) == len(orig_page.images)
        for orig_img, trans_img in zip(
            orig_page.images, trans_page.images, strict=True
        ):
            assert trans_img.image_id == orig_img.image_id
            assert trans_img.bbox.model_dump() == orig_img.bbox.model_dump()
            assert trans_img.width == orig_img.width
            assert trans_img.height == orig_img.height
            assert trans_img.format == orig_img.format

        # Check blocks preservation
        assert len(trans_page.blocks) == len(orig_page.blocks)
        for orig_blk, trans_blk in zip(
            orig_page.blocks, trans_page.blocks, strict=True
        ):
            assert trans_blk.reading_order == orig_blk.reading_order
            assert trans_blk.text == orig_blk.text
            assert trans_blk.bbox.model_dump() == orig_blk.bbox.model_dump()
            assert len(trans_blk.lines) == len(orig_blk.lines)
            for orig_ln, trans_ln in zip(orig_blk.lines, trans_blk.lines, strict=True):
                assert trans_ln.text == orig_ln.text
                assert trans_ln.bbox.model_dump() == orig_ln.bbox.model_dump()
                assert len(trans_ln.spans) == len(orig_ln.spans)
                for orig_sp, trans_sp in zip(
                    orig_ln.spans, trans_ln.spans, strict=True
                ):
                    assert trans_sp.font_name == orig_sp.font_name
                    assert trans_sp.font_size == orig_sp.font_size
                    assert trans_sp.color == orig_sp.color


@pytest.mark.asyncio
async def test_translation_engine_skips_empty_blocks() -> None:
    """Verify whitespace/empty blocks are not sent to translator and preserved as-is."""

    class TrackingTranslator(Translator):
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def translate(self, request: TranslationRequest) -> TranslationResult:
            self.calls.append(request.text)
            return TranslationResult(
                translated_text=f"[mock]{request.text}",
                detected_source_language="en",
                provider="mock",
            )

    tracker = TrackingTranslator()
    engine = TranslationEngine(tracker)
    doc = _create_minimal_document()

    translated = await engine.translate_document(doc, target_language="es")

    # p1-b1 is whitespace "   "
    p1_b1 = translated.pages[0].blocks[1]
    assert p1_b1.translated_text == "   "

    # Tracking translator should have been called only for non-empty blocks
    # Total non-empty blocks: p1-b0, p1-b2, p2-b0 -> 3 calls
    assert len(tracker.calls) == 3
    assert not any(c.strip() == "" for c in tracker.calls)


@pytest.mark.asyncio
async def test_translation_engine_context_propagation() -> None:
    """Verify previous_text and next_text context are correctly populated."""
    recorded_contexts = []

    class ContextInspectorTranslator(Translator):
        async def translate(self, request: TranslationRequest) -> TranslationResult:
            recorded_contexts.append((request.text, request.context))
            return TranslationResult(
                translated_text=f"[es]{request.text}",
                detected_source_language="en",
                provider="mock",
            )

    engine = TranslationEngine(ContextInspectorTranslator())
    doc = _create_minimal_document()

    await engine.translate_document(doc, target_language="es")

    # Page 1 has:
    # b0: "First heading" (prev=None, next="Body paragraph on page 1 with TRADUX-PRO.")
    # b1: "   " (skipped)
    # b2: "Body paragraph..." (prev="First heading", next=None)
    assert len(recorded_contexts) == 3

    text0, ctx0 = recorded_contexts[0]
    assert "First heading" in text0
    assert ctx0.page_number == 1
    assert ctx0.reading_order == 0
    assert ctx0.previous_text is None
    assert ctx0.next_text == "Body paragraph on page 1 with TRADUX-PRO."

    text2, ctx2 = recorded_contexts[1]
    assert "Body paragraph" in text2
    assert ctx2.page_number == 1
    assert ctx2.reading_order == 2
    assert ctx2.previous_text == "First heading"
    assert ctx2.next_text is None


@pytest.mark.asyncio
async def test_translation_engine_protected_terms_restoration() -> None:
    """Verify protected terms and tokens are preserved intact in translated document."""
    doc = _create_minimal_document()
    engine = TranslationEngine(MockTranslator())

    translated = await engine.translate_document(
        doc,
        target_language="fr",
        protected_terms=["TRADUX-PRO"],
    )

    p1_b2 = translated.pages[0].blocks[2]
    # In MockTranslator, text is wrapped with [FR], but TRADUX-PRO should be restored
    assert p1_b2.translated_text is not None
    assert "TRADUX-PRO" in p1_b2.translated_text
    assert "__TRX_PH_" not in p1_b2.translated_text


@pytest.mark.asyncio
async def test_translation_engine_fail_fast_on_provider_error() -> None:
    """Verify fail-fast behavior and exact location metadata on provider error."""

    class FailingTranslator(Translator):
        async def translate(self, request: TranslationRequest) -> TranslationResult:
            if request.context.page_number == 2:
                raise RuntimeError("Service unavailable at page 2")
            return TranslationResult(
                translated_text=f"[es]{request.text}",
                detected_source_language="en",
                provider="mock",
            )

    engine = TranslationEngine(FailingTranslator())
    doc = _create_minimal_document()

    with pytest.raises(TranslationProviderError) as exc_info:
        await engine.translate_document(doc, target_language="es")

    err = exc_info.value
    assert err.page_number == 2
    assert err.reading_order == 0
    assert "page=2" in str(err)
    assert "block=0" in str(err)


@pytest.mark.asyncio
async def test_translation_engine_fail_fast_on_integrity_error() -> None:
    """Verify TranslationIntegrityError reports precise page and block coordinates."""

    class CorruptingTranslator(Translator):
        async def translate(self, request: TranslationRequest) -> TranslationResult:
            # Corrupt the text by deleting all placeholders
            return TranslationResult(
                translated_text="Corrupted translation without tokens",
                detected_source_language="en",
                provider="mock",
            )

    engine = TranslationEngine(CorruptingTranslator())
    doc = _create_minimal_document()

    # Document p1-b2 has a protected term TRADUX-PRO
    with pytest.raises(TranslationIntegrityError) as exc_info:
        await engine.translate_document(
            doc,
            target_language="es",
            protected_terms=["TRADUX-PRO"],
        )

    err = exc_info.value
    assert err.page_number == 1
    assert err.reading_order == 2
    assert "page=1" in str(err)
    assert "block=2" in str(err)


@pytest.mark.asyncio
async def test_translation_engine_end_to_end_with_analyzer(
    sample_pdf_bytes: bytes,
) -> None:
    """Verify complete end-to-end flow: PDF -> Analyzer -> translate_document."""
    # 1. Analyze PDF into DocumentModel
    analyzer = DocumentAnalyzer()
    source_doc = analyzer.analyze_bytes(sample_pdf_bytes, filename="sample.pdf")
    assert source_doc.page_count >= 1

    # 2. Translate with MockTranslator
    engine = TranslationEngine(MockTranslator())
    translated_doc = await engine.translate_document(
        source_doc,
        target_language="es",
        protected_terms=["Tradux", "PyMuPDF"],
    )

    # 3. Verify translated document integrity
    assert translated_doc.filename == "sample.pdf"
    assert translated_doc.page_count == source_doc.page_count

    for page in translated_doc.pages:
        for blk in page.blocks:
            if blk.text.strip():
                assert blk.translated_text is not None
                assert blk.translated_text.startswith("[ES] ")
