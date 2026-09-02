"""Tests for application settings and configuration."""

import pytest

from app.core.config import Settings, get_settings


def test_default_settings() -> None:
    """Settings should load default values properly."""
    settings = Settings()
    assert settings.app_name == "Tradux"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.temp_dir == "temp"
    assert settings.output_dir == "output"
    assert settings.max_upload_size_mb == 50


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should honor environment variables."""
    monkeypatch.setenv("APP_NAME", "TraduxTest")
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("PORT", "9000")

    settings = Settings()
    assert settings.app_name == "TraduxTest"
    assert settings.environment == "testing"
    assert settings.debug is True
    assert settings.port == 9000


def test_get_settings_cached() -> None:
    """get_settings() should return a valid Settings instance."""
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.app_name == "Tradux"
