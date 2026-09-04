"""Pytest fixtures for Tradux test suite."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.fixtures.generator import create_sample_pdf_bytes, create_sample_pdf_file


@pytest.fixture
def client() -> TestClient:
    """Provide a FastAPI TestClient instance."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Provide deterministic sample PDF bytes in memory."""
    return create_sample_pdf_bytes()


@pytest.fixture
def sample_pdf_file(tmp_path: Path) -> Path:
    """Provide a deterministic sample PDF file on filesystem inside tmp_path."""
    target = tmp_path / "sample_document.pdf"
    return create_sample_pdf_file(target)
