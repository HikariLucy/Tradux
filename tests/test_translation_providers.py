"""Unit tests for translation providers and factory."""

import json

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import (
    TraduxError,
    TranslationError,
    TranslationProviderError,
    TranslationTimeoutError,
)
from app.translators.factory import get_translator
from app.translators.mock import MockTranslator
from app.translators.models import TranslationRequest, TranslationResult
from app.translators.openai import OpenAITranslator


@pytest.mark.asyncio
async def test_mock_translator_contract() -> None:
    """Verify MockTranslator determinism and placeholder preservation."""
    translator = MockTranslator()

    req = TranslationRequest(
        text="Hello __TRX_PH_000__ world",
        source_language="en",
        target_language="es",
    )
    result = await translator.translate(req)

    assert isinstance(result, TranslationResult)
    assert result.provider == "mock"
    assert result.model == "mock-v1"
    assert result.translated_text == "[ES] Hello __TRX_PH_000__ world"
    assert result.detected_source_language == "en"

    # Test custom mapping
    custom = MockTranslator(translation_map={"Hello": "Hola"})
    custom_res = await custom.translate(
        TranslationRequest(text="Hello", target_language="es")
    )
    assert custom_res.translated_text == "Hola"


@pytest.mark.asyncio
async def test_mock_translator_auto_detect() -> None:
    """Verify MockTranslator detection when source_language is None."""
    translator = MockTranslator(default_source_language="nl")
    req = TranslationRequest(text="Welkom bij Tradux", target_language="es")
    result = await translator.translate(req)

    assert result.detected_source_language == "nl"
    assert result.translated_text == "[ES] Welkom bij Tradux"


@pytest.mark.asyncio
async def test_openai_translator_success() -> None:
    """Verify OpenAITranslator handles successful Chat Completions response."""

    def handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content)
        assert data["model"] == "gpt-4o-mini"
        assert len(data["messages"]) == 2

        response_payload = {
            "choices": [{"message": {"content": "Hola Tradux", "role": "assistant"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        return httpx.Response(200, json=response_payload)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    settings = Settings(
        translation_provider="openai",
        translation_api_base_url="https://mock.api/v1",
        translation_api_key="test-key",
        translation_model="gpt-4o-mini",
    )
    translator = OpenAITranslator(settings=settings, client=client)

    req = TranslationRequest(
        text="Hello Tradux",
        source_language="en",
        target_language="es",
    )
    result = await translator.translate(req)

    assert result.provider == "openai"
    assert result.translated_text == "Hola Tradux"
    assert result.detected_source_language == "en"
    assert result.metrics.get("total_tokens") == 15


@pytest.mark.asyncio
async def test_openai_translator_auto_detect_json_response() -> None:
    """Verify OpenAITranslator parses structured JSON when source_language is None."""

    def handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content)
        assert data.get("response_format") == {"type": "json_object"}

        json_content = json.dumps(
            {
                "detected_source_language": "fr",
                "translated_text": "Tradux est magnifique",
            }
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json_content}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    settings = Settings(translation_api_key="test-key")
    translator = OpenAITranslator(settings=settings, client=client)

    req = TranslationRequest(
        text="Tradux is wonderful",
        source_language=None,
        target_language="fr",
    )
    result = await translator.translate(req)

    assert result.detected_source_language == "fr"
    assert result.translated_text == "Tradux est magnifique"


@pytest.mark.asyncio
async def test_openai_translator_timeout_normalized() -> None:
    """Verify provider timeout is converted to TranslationTimeoutError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Mock transport timeout")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    settings = Settings(translation_api_key="test-key")
    translator = OpenAITranslator(settings=settings, client=client)

    req = TranslationRequest(text="Hello", target_language="es")
    with pytest.raises(TranslationTimeoutError, match="timed out"):
        await translator.translate(req)


@pytest.mark.asyncio
async def test_openai_translator_http_error_normalized() -> None:
    """Verify non-2xx HTTP status is converted to TranslationProviderError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    settings = Settings(translation_api_key="test-key")
    translator = OpenAITranslator(settings=settings, client=client)

    req = TranslationRequest(text="Hello", target_language="es")
    with pytest.raises(TranslationProviderError, match="HTTP 500"):
        await translator.translate(req)


@pytest.mark.asyncio
async def test_openai_translator_empty_and_invalid_json() -> None:
    """Verify empty choices or corrupted JSON raises TranslationProviderError."""

    # 1. Empty choices
    def handler_empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    client_empty = httpx.AsyncClient(transport=httpx.MockTransport(handler_empty))
    settings = Settings(translation_api_key="test-key")
    translator_empty = OpenAITranslator(settings=settings, client=client_empty)

    with pytest.raises(TranslationProviderError, match="Empty choices"):
        await translator_empty.translate(
            TranslationRequest(text="Hello", target_language="es")
        )

    # 2. Invalid structured JSON for auto-detect
    def handler_bad_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not valid json"}}]},
        )

    client_bad = httpx.AsyncClient(transport=httpx.MockTransport(handler_bad_json))
    translator_bad = OpenAITranslator(settings=settings, client=client_bad)

    with pytest.raises(TranslationProviderError, match="Failed to parse structured"):
        await translator_bad.translate(
            TranslationRequest(text="Hello", source_language=None, target_language="es")
        )


@pytest.mark.asyncio
async def test_openai_defensive_root_json_is_list() -> None:
    """Verify TranslationProviderError when root response JSON is a list."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(translation_api_key="secret-key-123")
    translator = OpenAITranslator(settings=settings, client=client)

    with pytest.raises(TranslationProviderError, match="root must be an object") as exc:
        await translator.translate(
            TranslationRequest(text="Sensitive source text", target_language="es")
        )
    assert "secret-key-123" not in str(exc.value)
    assert "Sensitive source text" not in str(exc.value)


@pytest.mark.asyncio
async def test_openai_defensive_choice_not_dict() -> None:
    """Verify TranslationProviderError when choices[0] is not a dictionary."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": ["not-a-dict"]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(translation_api_key="secret-key-123")
    translator = OpenAITranslator(settings=settings, client=client)

    with pytest.raises(
        TranslationProviderError, match="'choices\\[0\\]' must be an object"
    ) as exc:
        await translator.translate(
            TranslationRequest(text="Sensitive source text", target_language="es")
        )
    assert "secret-key-123" not in str(exc.value)


@pytest.mark.asyncio
async def test_openai_defensive_message_not_dict() -> None:
    """Verify TranslationProviderError when message is not a dictionary."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": "not-a-dict"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(translation_api_key="secret-key-123")
    translator = OpenAITranslator(settings=settings, client=client)

    with pytest.raises(
        TranslationProviderError, match="'message' must be an object"
    ) as exc:
        await translator.translate(
            TranslationRequest(text="Sensitive source text", target_language="es")
        )
    assert "secret-key-123" not in str(exc.value)


@pytest.mark.asyncio
async def test_openai_defensive_content_not_str() -> None:
    """Verify TranslationProviderError when content is not a string."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": 12345}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(translation_api_key="secret-key-123")
    translator = OpenAITranslator(settings=settings, client=client)

    with pytest.raises(
        TranslationProviderError, match="'content' must be a non-empty string"
    ) as exc:
        await translator.translate(
            TranslationRequest(text="Sensitive source text", target_language="es")
        )
    assert "secret-key-123" not in str(exc.value)


@pytest.mark.asyncio
async def test_openai_defensive_autodetect_missing_detected_language() -> None:
    """Verify TranslationProviderError when auto-detect lacks
    detected_source_language.
    """
    content = json.dumps({"translated_text": "Texto"})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(translation_api_key="secret-key-123")
    translator = OpenAITranslator(settings=settings, client=client)

    with pytest.raises(
        TranslationProviderError, match="do not match expected contract"
    ) as exc:
        await translator.translate(
            TranslationRequest(
                text="Sensitive source text", source_language=None, target_language="es"
            )
        )
    assert "secret-key-123" not in str(exc.value)


@pytest.mark.asyncio
async def test_openai_defensive_autodetect_numeric_translated_text() -> None:
    """Verify TranslationProviderError when translated_text is numeric."""
    content = json.dumps({"detected_source_language": "en", "translated_text": 12345})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(translation_api_key="secret-key-123")
    translator = OpenAITranslator(settings=settings, client=client)

    with pytest.raises(
        TranslationProviderError, match="'translated_text' string"
    ) as exc:
        await translator.translate(
            TranslationRequest(
                text="Sensitive source text", source_language=None, target_language="es"
            )
        )
    assert "secret-key-123" not in str(exc.value)


@pytest.mark.asyncio
async def test_openai_defensive_autodetect_empty_detected_language() -> None:
    """Verify TranslationProviderError when detected_source_language is empty."""
    content = json.dumps({"detected_source_language": "  ", "translated_text": "Texto"})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(translation_api_key="secret-key-123")
    translator = OpenAITranslator(settings=settings, client=client)

    with pytest.raises(
        TranslationProviderError, match="'detected_source_language' string"
    ) as exc:
        await translator.translate(
            TranslationRequest(
                text="Sensitive source text", source_language=None, target_language="es"
            )
        )
    assert "secret-key-123" not in str(exc.value)


def test_factory_selection() -> None:
    """Verify factory returns appropriate provider according to configuration."""
    # Mock works without API key
    mock_t = get_translator("mock")
    assert isinstance(mock_t, MockTranslator)

    # OpenAI without API key raises configuration TraduxError
    empty_settings = Settings(translation_api_key=None)
    with pytest.raises(TraduxError, match="requires TRANSLATION_API_KEY"):
        get_translator("openai", settings=empty_settings)

    # OpenAI with configured API key succeeds
    valid_settings = Settings(translation_api_key="sk-test-key")
    openai_t = get_translator("openai", settings=valid_settings)
    assert isinstance(openai_t, OpenAITranslator)

    # Unsupported provider raises TraduxError
    with pytest.raises(TraduxError, match="Unsupported translation provider"):
        get_translator("unsupported_provider_xyz")


def test_environment_variables_propagation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify flat environment variables propagate to Settings and get_translator."""
    from app.core.config import get_settings

    secret_key = "sk-env-secret-value-777"
    monkeypatch.setenv("TRANSLATION_PROVIDER", "openai")
    monkeypatch.setenv("TRANSLATION_API_BASE_URL", "https://env.api.com/v1")
    monkeypatch.setenv("TRANSLATION_API_KEY", secret_key)
    monkeypatch.setenv("TRANSLATION_MODEL", "gpt-4o")
    monkeypatch.setenv("TRANSLATION_TIMEOUT_SECONDS", "18.5")

    # Clear cache to reload settings from monkeypatched environment
    get_settings.cache_clear()
    try:
        settings = Settings()
        assert settings.translation_provider == "openai"
        assert settings.translation_api_base_url == "https://env.api.com/v1"
        assert settings.translation_api_key is not None
        assert settings.translation_api_key.get_secret_value() == secret_key
        assert settings.translation_model == "gpt-4o"
        assert settings.translation_timeout_seconds == 18.5

        # Key must never leak in repr or str of Settings
        assert secret_key not in repr(settings)
        assert secret_key not in str(settings)

        # Propagates cleanly into get_translator
        translator = get_translator()
        assert isinstance(translator, OpenAITranslator)
        assert translator.base_url == "https://env.api.com/v1"
        assert translator.model == "gpt-4o"
        assert translator.timeout_seconds == 18.5
        assert translator.api_key == secret_key

        # Key must never leak in repr of OpenAITranslator
        assert secret_key not in repr(translator)
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_no_leak_of_content_or_credentials_in_errors() -> None:
    """Verify exceptions never leak sensitive text or API keys across error modes."""
    from app.domain.models import BoundingBox, Document, Page, TextBlock
    from app.translators.engine import TranslationEngine

    secret_text = "SUPER_SECRET_DOCUMENT_TEXT_123"
    secret_key = "sk-test-secret-value"
    settings = Settings(
        translation_api_key=secret_key,
        translation_timeout_seconds=5.0,
    )

    req = TranslationRequest(text=secret_text, target_language="es")

    # 1. Mode a: Timeout
    def handler_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Timeout")

    t_timeout = OpenAITranslator(
        settings=settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler_timeout)),
    )
    with pytest.raises(TranslationTimeoutError) as exc_info:
        await t_timeout.translate(req)
    assert secret_text not in str(exc_info.value)
    assert secret_key not in str(exc_info.value)
    assert secret_key not in repr(exc_info.value)

    # 2. Mode b: HTTP 500
    def handler_500(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text=f"Internal crash with {secret_text}")

    t_500 = OpenAITranslator(
        settings=settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler_500)),
    )
    with pytest.raises(TranslationProviderError) as exc_info:
        await t_500.translate(req)
    assert secret_text not in str(exc_info.value)
    assert secret_key not in str(exc_info.value)
    assert secret_key not in repr(exc_info.value)

    # 3. Mode c: Invalid JSON response
    def handler_bad_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="{broken_json_payload")

    t_bad_json = OpenAITranslator(
        settings=settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler_bad_json)),
    )
    with pytest.raises(TranslationProviderError) as exc_info:
        await t_bad_json.translate(req)
    assert secret_text not in str(exc_info.value)
    assert secret_key not in str(exc_info.value)
    assert secret_key not in repr(exc_info.value)

    # 4. Mode d: Integrity failure through TranslationEngine
    class CorruptingTranslator:
        async def translate(self, r: TranslationRequest) -> TranslationResult:
            return TranslationResult(
                translated_text="Dropped placeholders completely",
                detected_source_language="en",
                provider="mock",
            )

    bbox = BoundingBox(x0=10.0, y0=10.0, x1=50.0, y1=20.0)
    doc = Document(
        filename="confidential.pdf",
        pages=[
            Page(
                page_number=1,
                width=100.0,
                height=100.0,
                blocks=[
                    TextBlock(
                        text=secret_text,
                        bbox=bbox,
                        reading_order=0,
                    )
                ],
            )
        ],
    )
    engine = TranslationEngine(CorruptingTranslator())
    with pytest.raises(TranslationError) as exc_info:
        await engine.translate_document(
            doc, target_language="es", protected_terms=[secret_text]
        )

    # Must contain safe metadata without leaking document text or credentials
    err_str = str(exc_info.value)
    assert secret_text not in err_str
    assert secret_key not in err_str
    assert "page=1" in err_str
    assert "block=0" in err_str
