"""Tests for Phase 2.5 Tradux Web Workbench."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.models import (
    BoundingBox,
    Document,
    ImageElement,
    Page,
    TextBlock,
    TextLine,
    TextSpan,
)
from app.main import app


def _create_sample_document() -> Document:
    """Create a realistic sample Document model for testing."""
    bbox1 = BoundingBox(x0=50.0, y0=50.0, x1=200.0, y1=70.0)
    span1 = TextSpan(
        text="Introduction to Tradux",
        bbox=bbox1,
        font_name="Helvetica-Bold",
        font_size=14.0,
        color="#000000",
        flags=0,
    )
    line1 = TextLine(text="Introduction to Tradux", bbox=bbox1, spans=[span1])
    b0 = TextBlock(
        bbox=bbox1,
        text="Introduction to Tradux",
        lines=[line1],
        reading_order=0,
    )

    bbox2 = BoundingBox(x0=50.0, y0=80.0, x1=400.0, y1=120.0)
    span2 = TextSpan(
        text="This manual covers MODEL-X100 with ISO-9001 certification.",
        bbox=bbox2,
        font_name="Helvetica",
        font_size=10.0,
        color="#323232",
        flags=0,
    )
    line2 = TextLine(
        text="This manual covers MODEL-X100 with ISO-9001 certification.",
        bbox=bbox2,
        spans=[span2],
    )
    b1 = TextBlock(
        bbox=bbox2,
        text="This manual covers MODEL-X100 with ISO-9001 certification.",
        lines=[line2],
        reading_order=1,
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
        width=595.3,
        height=841.9,
        rotation=0,
        blocks=[b0, b1],
        images=[img],
    )

    return Document(
        filename="sample.pdf",
        page_count=1,
        pages=[p1],
    )


def test_workbench_index_html_returned() -> None:
    """Requirement 1: GET / returns 200 and HTML of the Workbench."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Tradux" in response.text
    assert "Mesa de traducción documental" in response.text


def test_workbench_static_assets_servable() -> None:
    """Requirement 2: Static assets (CSS and JS) are servable."""
    client = TestClient(app)

    # CSS
    css_res = client.get("/static/workbench.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers.get("content-type", "")
    assert "--bg-canvas" in css_res.text
    assert ".demo-notice-banner" in css_res.text

    # JS
    js_res = client.get("/static/workbench.js")
    assert js_res.status_code == 200
    content_type = js_res.headers.get("content-type", "")
    assert "javascript" in content_type or "text/plain" in content_type
    assert "Tradux Web Workbench" in js_res.text


def test_workbench_html_structure_without_js() -> None:
    """Requirement 3: The HTML contains critical UI elements structurally."""
    client = TestClient(app)
    response = client.get("/")
    html = response.text

    # Critical header and branding
    assert "app-header" in html
    assert "brand-name" in html
    assert "Mesa de traducción documental" in html

    # Critical dropzone and file input
    assert "dropzone" in html
    assert 'id="pdf-file-input"' in html
    assert 'id="btn-analyze"' in html

    # Critical structural panels
    assert "workspace-grid" in html
    assert "panel-structure" in html
    assert "panel-preview" in html
    assert "panel-translation" in html
    assert "panel-blocks" in html

    # Critical translation controls & pipeline stepper
    assert "stepper-list" in html
    assert 'id="select-source-lang"' in html
    assert 'id="select-target-lang"' in html
    assert 'id="input-protected-term"' in html
    assert 'id="btn-translate"' in html
    assert "Modo de demostración" in html
    assert "Generar vista previa" in html

    # Critical blocks table
    assert "blocks-table" in html
    assert 'id="blocks-tbody"' in html


def test_workbench_translate_valid_document() -> None:
    """Requirement 4 & 5: POST /api/v1/workbench/translate accepts valid Document
    and returns mode='mock'.
    """
    client = TestClient(app)
    doc = _create_sample_document()

    payload = {
        "document": doc.model_dump(),
        "source_language": "en",
        "target_language": "es",
        "protected_terms": ["Tradux"],
    }

    response = client.post("/api/v1/workbench/translate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["mode"] == "mock"
    assert data["translated_blocks"] == 2
    assert "document" in data
    assert data["document"]["filename"] == "sample.pdf"


def test_workbench_translate_populates_translated_and_keeps_source() -> None:
    """Requirements 6 & 7: translated_text is populated by real TranslationEngine
    while source text remains intact.
    """
    client = TestClient(app)
    doc = _create_sample_document()

    payload = {
        "document": doc.model_dump(),
        "source_language": "en",
        "target_language": "es",
        "protected_terms": [],
    }

    response = client.post("/api/v1/workbench/translate", json=payload)
    assert response.status_code == 200

    res_doc = response.json()["document"]
    p1 = res_doc["pages"][0]

    # Block 0: check source intact and translated_text populated
    b0 = p1["blocks"][0]
    assert b0["text"] == "Introduction to Tradux"
    assert b0["translated_text"] is not None
    assert b0["translated_text"].startswith("[ES]")
    assert "Introduction to Tradux" in b0["translated_text"]

    # Block 1
    b1 = p1["blocks"][1]
    assert b1["text"] == "This manual covers MODEL-X100 with ISO-9001 certification."
    assert b1["translated_text"] is not None
    assert b1["translated_text"].startswith("[ES]")


def test_workbench_translate_preserves_geometry_and_images() -> None:
    """Requirement 8: Geometry, bounding boxes, and images remain intact."""
    client = TestClient(app)
    doc = _create_sample_document()

    payload = {
        "document": doc.model_dump(),
        "source_language": "en",
        "target_language": "es",
    }

    response = client.post("/api/v1/workbench/translate", json=payload)
    assert response.status_code == 200

    res_doc = response.json()["document"]
    p1 = res_doc["pages"][0]

    # Verify Page geometry
    assert p1["width"] == 595.3
    assert p1["height"] == 841.9
    assert p1["rotation"] == 0

    # Verify Block 0 bbox
    assert p1["blocks"][0]["bbox"] == {
        "x0": 50.0,
        "y0": 50.0,
        "x1": 200.0,
        "y1": 70.0,
    }

    # Verify Image Element intact
    assert len(p1["images"]) == 1
    img = p1["images"][0]
    assert img["image_id"] == "p001-img001"
    assert img["bbox"] == {
        "x0": 50.0,
        "y0": 200.0,
        "x1": 250.0,
        "y1": 350.0,
    }
    assert img["width"] == 200
    assert img["height"] == 150
    assert img["format"] == "png"


def test_workbench_translate_with_protected_terms() -> None:
    """Requirement 9: Protected terms are preserved through the endpoint."""
    client = TestClient(app)
    doc = _create_sample_document()

    payload = {
        "document": doc.model_dump(),
        "source_language": "en",
        "target_language": "fr",
        "protected_terms": ["MODEL-X100", "ISO-9001"],
    }

    response = client.post("/api/v1/workbench/translate", json=payload)
    assert response.status_code == 200

    res_doc = response.json()["document"]
    b1 = res_doc["pages"][0]["blocks"][1]

    assert "MODEL-X100" in b1["translated_text"]
    assert "ISO-9001" in b1["translated_text"]
    assert "__TRX_PH_" not in b1["translated_text"]


def test_workbench_translate_invalid_payload_returns_422() -> None:
    """Requirement 10: Invalid document payload returns 422 without 500."""
    client = TestClient(app)

    # Missing document
    res1 = client.post("/api/v1/workbench/translate", json={"target_language": "es"})
    assert res1.status_code == 422

    # Malformed document
    res2 = client.post(
        "/api/v1/workbench/translate",
        json={"document": {"pages": "not-a-list"}, "target_language": "es"},
    )
    assert res2.status_code == 422


def test_workbench_translate_forces_mock_even_when_settings_are_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement 11: Endpoint strictly forces MockTranslator even if settings
    specify translation_provider='openai'.
    """
    monkeypatch.setenv("TRANSLATION_PROVIDER", "openai")
    monkeypatch.setenv("TRANSLATION_API_KEY", "sk-live-mock-test")

    # Create fresh settings instance verifying env vars took effect
    test_settings = Settings()
    assert test_settings.translation_provider == "openai"

    client = TestClient(app)
    doc = _create_sample_document()

    payload = {
        "document": doc.model_dump(),
        "source_language": None,
        "target_language": "es",
    }

    # Must succeed 100% offline without attempting any network call to OpenAI
    response = client.post("/api/v1/workbench/translate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "mock"
    assert data["translated_blocks"] == 2
