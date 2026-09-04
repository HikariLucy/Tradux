"""Translation domain models and request/response specifications."""

from typing import Any

from pydantic import BaseModel, Field


class TranslationContext(BaseModel):
    """Surrounding context provided to the translator for reference only."""

    previous_text: str | None = Field(
        default=None,
        description="Text of preceding block on the same page",
    )
    next_text: str | None = Field(
        default=None,
        description="Text of succeeding block on the same page",
    )
    page_number: int | None = Field(
        default=None,
        description="1-indexed page number of the block",
    )
    reading_order: int | None = Field(
        default=None,
        description="0-indexed reading order within the page",
    )


class TranslationRequest(BaseModel):
    """Specification of a text block to be translated."""

    text: str = Field(
        ...,
        description="Text to translate, possibly containing protected placeholders",
    )
    source_language: str | None = Field(
        default=None,
        description="Source language code (ISO 639-1); None triggers auto-detection",
    )
    target_language: str = Field(
        ...,
        description="Target language code (ISO 639-1), e.g. 'es'",
    )
    context: TranslationContext | None = Field(
        default=None,
        description="Optional adjacent context for disambiguation",
    )
    protected_terms: list[str] = Field(
        default_factory=list,
        description="List of terms that must be preserved without translation",
    )


class TranslationResult(BaseModel):
    """Outcome of a translation operation produced by a Translator provider."""

    translated_text: str = Field(
        ...,
        description="Translated text with placeholders preserved",
    )
    detected_source_language: str | None = Field(
        default=None,
        description="Detected source language code when auto-detection is performed",
    )
    provider: str = Field(
        ...,
        description="Identifier of the provider (e.g. 'mock', 'openai')",
    )
    model: str | None = Field(
        default=None,
        description="Model name used by the provider",
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Primitive usage or timing metrics if reported by provider",
    )
