"""Decoupled translation provider interfaces and implementations (Phase 2)."""

from app.translators.base import Translator
from app.translators.engine import TranslationEngine
from app.translators.factory import get_translator
from app.translators.mock import MockTranslator
from app.translators.models import (
    TranslationContext,
    TranslationRequest,
    TranslationResult,
)
from app.translators.openai import OpenAITranslator

__all__ = [
    "MockTranslator",
    "OpenAITranslator",
    "TranslationContext",
    "TranslationEngine",
    "TranslationRequest",
    "TranslationResult",
    "Translator",
    "get_translator",
]
