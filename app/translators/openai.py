"""OpenAI-compatible Chat Completions HTTP translation adapter."""

import json
import logging

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import TranslationProviderError, TranslationTimeoutError
from app.translators.models import TranslationRequest, TranslationResult

logger = logging.getLogger(__name__)


class OpenAITranslator:
    """Translation provider using standard OpenAI-compatible Chat Completions API."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize OpenAITranslator.

        Args:
            settings: Application settings containing translation configuration.
            client: Optional pre-configured httpx.AsyncClient (e.g. for testing).
        """
        cfg = settings or get_settings()
        self.base_url = cfg.translation_api_base_url.rstrip("/")
        if hasattr(cfg.translation_api_key, "get_secret_value"):
            self.api_key = cfg.translation_api_key.get_secret_value()
        elif cfg.translation_api_key:
            self.api_key = str(cfg.translation_api_key)
        else:
            self.api_key = None

        self.model = cfg.translation_model
        self.timeout_seconds = cfg.translation_timeout_seconds
        self._external_client = client

    def __repr__(self) -> str:
        return (
            f"OpenAITranslator(base_url='{self.base_url}', "
            f"model='{self.model}', timeout={self.timeout_seconds})"
        )

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate a text block via OpenAI-compatible Chat Completions API."""
        if not self.api_key or not self.api_key.strip():
            raise TranslationProviderError(
                "OpenAI translation provider requires "
                "TRANSLATION_API_KEY to be configured"
            )

        endpoint = f"{self.base_url}/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Construct system and user messages
        auto_detect = request.source_language is None

        system_prompt = (
            f"You are a professional document translator. Translate the input text "
            f"into target language '{request.target_language}'.\n"
            f"Strict rules:\n"
            f"1. Never modify, translate, or remove tokens matching the pattern "
            f"'__TRX_PH_\\d+__'. Preserve them exactly as they appear.\n"
            f"2. Any provided context is strictly for disambiguation; do not "
            f"include context in the output.\n"
        )

        if auto_detect:
            system_prompt += (
                "3. Respond with a strict JSON object with exactly two keys: "
                "'detected_source_language' (ISO 639-1 code) and 'translated_text'."
            )
        else:
            system_prompt += "3. Return ONLY the translated text, without commentary."

        user_content_parts = []
        if request.context:
            if request.context.previous_text:
                user_content_parts.append(
                    f"[CONTEXT PREVIOUS]: {request.context.previous_text}"
                )
            if request.context.next_text:
                user_content_parts.append(
                    f"[CONTEXT NEXT]: {request.context.next_text}"
                )

        user_content_parts.append(f"[TEXT TO TRANSLATE]:\n{request.text}")
        user_message = "\n\n".join(user_content_parts)

        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.1,
        }

        if auto_detect:
            payload["response_format"] = {"type": "json_object"}

        timeout = httpx.Timeout(self.timeout_seconds)

        try:
            if self._external_client:
                response = await self._external_client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                    )
        except httpx.TimeoutException:
            raise TranslationTimeoutError(
                f"Translation request timed out after {self.timeout_seconds}s"
            ) from None
        except httpx.RequestError as e:
            raise TranslationProviderError(
                f"Network error communicating with provider: {type(e).__name__}"
            ) from None

        if response.status_code != 200:
            raise TranslationProviderError(
                f"Translation provider returned HTTP {response.status_code}"
            )

        try:
            data = response.json()
        except Exception as e:
            raise TranslationProviderError(
                f"Failed to parse JSON response: {type(e).__name__}"
            ) from None

        choices = data.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            raise TranslationProviderError(
                "Empty choices returned by translation provider"
            )

        raw_content = choices[0].get("message", {}).get("content", "")
        if not raw_content or not raw_content.strip():
            raise TranslationProviderError(
                "Empty translation content returned by provider"
            )

        detected_language = request.source_language
        translated_text = raw_content.strip()

        if auto_detect:
            try:
                parsed_json = json.loads(translated_text)
                detected_language = parsed_json.get("detected_source_language")
                translated_text = str(parsed_json.get("translated_text", ""))
            except Exception as e:
                raise TranslationProviderError(
                    f"Failed to parse structured translation JSON: {type(e).__name__}"
                ) from None

            if not translated_text:
                raise TranslationProviderError(
                    "Structured response did not contain valid 'translated_text'"
                )

        usage = data.get("usage", {})
        metrics = {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }

        return TranslationResult(
            translated_text=translated_text,
            detected_source_language=detected_language,
            provider="openai",
            model=self.model,
            metrics={k: v for k, v in metrics.items() if v is not None},
        )
