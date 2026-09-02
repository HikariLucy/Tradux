"""Pytest fixtures for Tradux test suite."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Provide a FastAPI TestClient instance."""
    app = create_app()
    return TestClient(app)
