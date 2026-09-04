"""Factory for selecting and instantiating translation providers."""

from app.core.config import Settings, get_settings
from app.core.errors import TraduxError
from app.translators.base import Translator
from app.translators.mock import MockTranslator
from app.translators.openai import OpenAITranslator


def get_translator(
    provider: str | None = None,
    settings: Settings | None = None,
) -> Translator:
    """Instantiate and return the configured translation provider.

    Args:
        provider: Provider identifier ('mock' or 'openai'), or None for config default.
        settings: Optional custom application settings.

    Returns:
        Translator instance.

    Raises:
        TraduxError: If the specified provider is unsupported.
    """
    cfg = settings or get_settings()
    active_provider = (provider or cfg.translation_provider).strip().lower()

    if active_provider == "mock":
        return MockTranslator()
    if active_provider in ("openai", "chatgpt"):
        key = (
            cfg.translation_api_key.get_secret_value()
            if hasattr(cfg.translation_api_key, "get_secret_value")
            else cfg.translation_api_key
        )
        if not key or not str(key).strip():
            raise TraduxError(
                "OpenAI translation provider requires "
                "TRANSLATION_API_KEY to be configured"
            )
        return OpenAITranslator(settings=cfg)

    raise TraduxError(f"Unsupported translation provider: '{active_provider}'")
