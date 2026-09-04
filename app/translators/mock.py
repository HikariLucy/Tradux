"""Deterministic mock translation provider for offline development and testing."""

from app.translators.models import TranslationRequest, TranslationResult


class MockTranslator:
    """Deterministic mock translation provider without network calls."""

    def __init__(
        self,
        translation_map: dict[str, str] | None = None,
        default_source_language: str = "en",
    ) -> None:
        """Initialize MockTranslator.

        Args:
            translation_map: Optional dict mapping input text to exact output text.
            default_source_language: Fallback language code when detection is triggered.
        """
        self.translation_map = translation_map or {}
        self.default_source_language = default_source_language

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """Deterministically translate the request text.

        Preserves all placeholder tokens verbatim.
        """
        # Auto-detect language if source_language is None
        detected_language = request.source_language or self.default_source_language

        # Check explicit mapping first
        if request.text in self.translation_map:
            translated_text = self.translation_map[request.text]
        else:
            # Synthetic deterministic translation prefixing target language code
            prefix = f"[{request.target_language.upper()}] "
            translated_text = f"{prefix}{request.text}"

        return TranslationResult(
            translated_text=translated_text,
            detected_source_language=detected_language,
            provider="mock",
            model="mock-v1",
            metrics={"character_count": len(request.text)},
        )
