"""Abstract interface definition for decoupled translation providers."""

from typing import Protocol, runtime_checkable

from app.translators.models import TranslationRequest, TranslationResult


@runtime_checkable
class Translator(Protocol):
    """Decoupled interface for translation providers."""

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate a single request into the target language.

        Args:
            request: TranslationRequest containing text, languages, and context.

        Returns:
            TranslationResult with translated text and metadata.

        Raises:
            TranslationError: Upon timeout, HTTP failure, or integrity violations.
        """
        ...
