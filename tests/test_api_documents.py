"""Integration tests for POST /api/v1/documents/analyze endpoint."""

import io

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from tests.fixtures.generator import create_encrypted_pdf_bytes, create_sample_pdf_bytes


def test_api_analyze_valid_pdf(client: TestClient, sample_pdf_bytes: bytes) -> None:
    """Verify uploading valid PDF returns HTTP 200 and Document JSON."""
    response = client.post(
        "/api/v1/documents/analyze",
        files={"file": ("sample.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["filename"] == "sample.pdf"
    assert data["page_count"] == 2
    assert len(data["pages"]) == 2

    # Check page 1 structure
    p1 = data["pages"][0]
    assert p1["page_number"] == 1
    assert p1["width"] > 0
    assert p1["height"] > 0
    assert len(p1["blocks"]) >= 3
    assert len(p1["images"]) == 2

    # Check block structure
    b0 = p1["blocks"][0]
    assert "text" in b0
    assert "bbox" in b0
    assert "lines" in b0
    assert len(b0["lines"]) >= 1

    # Check spans and colors
    s0 = b0["lines"][0]["spans"][0]
    assert s0["color"].startswith("#")
    assert len(s0["color"]) == 7


def test_api_analyze_non_pdf_extension(client: TestClient) -> None:
    """Verify that non-PDF file extension is rejected with HTTP 400."""
    response = client.post(
        "/api/v1/documents/analyze",
        files={"file": ("document.txt", io.BytesIO(b"Plain text"), "text/plain")},
    )
    assert response.status_code == 400
    assert "not a PDF" in response.json()["detail"]


def test_api_analyze_corrupt_pdf(client: TestClient) -> None:
    """Verify that corrupt PDF content is rejected with HTTP 400."""
    response = client.post(
        "/api/v1/documents/analyze",
        files={
            "file": ("corrupt.pdf", io.BytesIO(b"corrupt bytes"), "application/pdf")
        },
    )
    assert response.status_code == 400
    assert "Invalid or corrupted PDF" in response.json()["detail"]


def test_api_analyze_empty_file(client: TestClient) -> None:
    """Verify that 0-byte file is rejected with HTTP 400."""
    response = client.post(
        "/api/v1/documents/analyze",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_api_analyze_encrypted_pdf(client: TestClient) -> None:
    """Verify that password-protected PDF returns HTTP 422."""
    enc_bytes = create_encrypted_pdf_bytes(password="secret")
    response = client.post(
        "/api/v1/documents/analyze",
        files={"file": ("protected.pdf", io.BytesIO(enc_bytes), "application/pdf")},
    )
    assert response.status_code == 422
    assert "password-protected" in response.json()["detail"].lower()


def test_api_analyze_oversized_file(monkeypatch) -> None:
    """Verify that files exceeding MAX_UPLOAD_SIZE_MB return HTTP 413."""
    app = create_app()
    client = TestClient(app)

    # Temporarily set max_upload_size_mb to 0 MB via monkeypatch
    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)

    sample_bytes = create_sample_pdf_bytes()
    response = client.post(
        "/api/v1/documents/analyze",
        files={"file": ("large.pdf", io.BytesIO(sample_bytes), "application/pdf")},
    )
    assert response.status_code == 413
    assert "exceeds maximum permitted limit" in response.json()["detail"]
