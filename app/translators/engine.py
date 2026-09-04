"""Translation engine coordinating document-level translation workflows."""

import logging

from app.core.errors import TranslationError, TranslationProviderError
from app.domain.models import Document
from app.translators.base import Translator
from app.translators.factory import get_translator
from app.translators.models import TranslationContext, TranslationRequest
from app.translators.protection import mask_protected_tokens, restore_protected_tokens

logger = logging.getLogger(__name__)


class TranslationEngine:
    """Service that applies decoupled translation over structured Document models."""

    def __init__(self, translator: Translator | None = None) -> None:
        """Initialize TranslationEngine with a translator provider.

        Args:
            translator: Translator provider instance; defaults to get_translator().
        """
        self.translator = translator or get_translator()

    async def translate_document(
        self,
        document: Document,
        source_language: str | None = None,
        target_language: str = "es",
        protected_terms: list[str] | None = None,
    ) -> Document:
        """Translate a Document into target_language producing a deep translated copy.

        Preserves the source Document completely unmodified. All bounding boxes,
        fonts, sizes, colors, images, and structural hierarchy remain identical.

        Args:
            document: Source Document domain model.
            source_language: Optional source language code (None = auto-detect).
            target_language: Target language code (e.g. 'es').
            protected_terms: Optional list of terms to protect from translation.

        Returns:
            A new Document instance with translated_text populated in TextBlocks.

        Raises:
            TranslationError: Fail-fast on provider error or integrity violation,
                including page_number and reading_order location.
        """
        # Deep clone ensures source document is strictly immutable
        translated_doc = document.model_copy(deep=True)

        for page in translated_doc.pages:
            # Deterministic iteration in reading order
            sorted_blocks = sorted(page.blocks, key=lambda b: b.reading_order)
            num_blocks = len(sorted_blocks)

            for idx, block in enumerate(sorted_blocks):
                # Cleanly skip empty or whitespace-only blocks
                if not block.text or not block.text.strip():
                    block.translated_text = block.text
                    continue

                # Build context from previous and next non-empty blocks on the same page
                prev_text = None
                for p_idx in range(idx - 1, -1, -1):
                    cand = sorted_blocks[p_idx].text
                    if cand and cand.strip():
                        prev_text = cand
                        break

                next_text = None
                for n_idx in range(idx + 1, num_blocks):
                    cand = sorted_blocks[n_idx].text
                    if cand and cand.strip():
                        next_text = cand
                        break

                context = TranslationContext(
                    previous_text=prev_text,
                    next_text=next_text,
                    page_number=page.page_number,
                    reading_order=block.reading_order,
                )

                # Mask protected tokens and explicit terms
                masked_text, token_map = mask_protected_tokens(
                    block.text,
                    protected_terms=protected_terms,
                )

                req = TranslationRequest(
                    text=masked_text,
                    source_language=source_language,
                    target_language=target_language,
                    context=context,
                    protected_terms=protected_terms or [],
                )

                # Execute translation with fail-fast error localization
                try:
                    res = await self.translator.translate(req)
                except TranslationError as e:
                    if e.page_number is None:
                        e.page_number = page.page_number
                    if e.reading_order is None:
                        e.reading_order = block.reading_order
                    raise e
                except Exception as e:
                    raise TranslationProviderError(
                        f"Translation provider failed: {type(e).__name__}",
                        page_number=page.page_number,
                        reading_order=block.reading_order,
                    ) from None

                # Restore protected tokens and validate integrity
                restored_text = restore_protected_tokens(
                    res.translated_text,
                    token_map,
                    source_text=block.text,
                    page_number=page.page_number,
                    reading_order=block.reading_order,
                )

                block.translated_text = restored_text

        return translated_doc
