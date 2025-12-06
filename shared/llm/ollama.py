"""
Ollama Provider
===============

Local LLM provider using Ollama for cost optimization.

Version: 0.1.0
"""

import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from shared.config import settings
from shared.llm.provider import LLMMessage, LLMProvider, LLMResponse, LLMUsage
from shared.logging import get_logger


logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """
    Ollama local LLM provider.

    Supports any model available through Ollama, including:
    - Llama 3.3 (70B, 8B)
    - Mistral
    - CodeLlama
    - etc.
    """

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """
        Initialize Ollama provider.

        Args:
            host: Ollama server URL (default from settings)
            model: Model to use (default from settings)
            timeout: Request timeout in seconds
        """
        self._host = host or settings.llm.ollama.host
        self._model = model or settings.llm.ollama.model
        self._timeout = timeout or settings.llm.timeout_seconds

        # HTTP client for API calls
        self._client = httpx.AsyncClient(
            base_url=self._host,
            timeout=httpx.Timeout(self._timeout),
        )

        logger.debug(
            "ollama_provider_initialized",
            host=self._host,
            model=self._model,
        )

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    def _format_messages(self, messages: list[LLMMessage]) -> str:
        """
        Format messages into a prompt string.

        Ollama's chat API expects a specific format, but we can also
        use the generate API with a formatted prompt.
        """
        formatted = []

        for msg in messages:
            msg_dict = msg.to_dict()
            role = msg_dict["role"]
            content = msg_dict["content"]

            if role == "system":
                formatted.append(f"System: {content}")
            elif role == "user":
                formatted.append(f"Human: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")

        formatted.append("Assistant:")
        return "\n\n".join(formatted)

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        stop=stop_after_attempt(settings.llm.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        before_sleep=lambda retry_state: logger.warning(
            "ollama_retry",
            attempt=retry_state.attempt_number,
        ),
    )
    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop_sequences: list[str] | None = None,
    ) -> LLMResponse:
        """
        Generate a completion using Ollama.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Max tokens (num_predict in Ollama)
            stop_sequences: Stop sequences

        Returns:
            LLMResponse with generated content
        """
        start_time = time.perf_counter()

        # Use chat API for better multi-turn support
        chat_messages = []
        for msg in messages:
            msg_dict = msg.to_dict()
            chat_messages.append(
                {
                    "role": msg_dict["role"],
                    "content": msg_dict["content"],
                }
            )

        # Build options
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        else:
            options["temperature"] = settings.llm.temperature

        if max_tokens is not None:
            options["num_predict"] = max_tokens

        if stop_sequences:
            options["stop"] = stop_sequences

        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": chat_messages,
                    "stream": False,
                    "options": options,
                },
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract content
            content = data.get("message", {}).get("content", "")

            # Token usage (Ollama provides these in response)
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)

            usage = LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                # Local models have no API cost
                input_cost=0.0,
                output_cost=0.0,
                total_cost=0.0,
            )

            logger.debug(
                "ollama_completion",
                model=self._model,
                tokens=usage.total_tokens,
                latency_ms=round(latency_ms, 2),
            )

            return LLMResponse(
                content=content,
                model=data.get("model", self._model),
                provider=self.name,
                usage=usage,
                finish_reason=data.get("done_reason"),
                latency_ms=latency_ms,
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "ollama_http_error",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise
        except Exception as e:
            logger.error("ollama_error", error=str(e), error_type=type(e).__name__)
            raise

    async def health_check(self) -> dict[str, Any]:
        """
        Check Ollama server health and model availability.

        Returns:
            dict with status and available models
        """
        try:
            start = time.perf_counter()

            # Check if server is running
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.perf_counter() - start) * 1000

            # Get available models
            models = [m["name"] for m in data.get("models", [])]
            model_available = any(self._model in m for m in models)

            return {
                "status": "healthy" if model_available else "degraded",
                "provider": self.name,
                "model": self._model,
                "model_available": model_available,
                "available_models": models[:5],  # First 5
                "latency_ms": round(latency_ms, 2),
            }

        except httpx.ConnectError:
            logger.warning("ollama_not_running")
            return {
                "status": "unhealthy",
                "provider": self.name,
                "model": self._model,
                "error": "Ollama server not running",
            }
        except Exception as e:
            logger.error("ollama_health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "provider": self.name,
                "model": self._model,
                "error": str(e),
            }

    async def list_models(self) -> list[dict[str, Any]]:
        """
        List available models in Ollama.

        Returns:
            List of model info dicts
        """
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            logger.error("ollama_list_models_error", error=str(e))
            return []

    async def pull_model(self, model_name: str) -> bool:
        """
        Pull a model from Ollama library.

        Args:
            model_name: Model to pull (e.g., "llama3.3:70b")

        Returns:
            True if successful
        """
        try:
            logger.info("ollama_pulling_model", model=model_name)

            # This is a streaming endpoint, but we'll just wait for completion
            response = await self._client.post(
                "/api/pull",
                json={"name": model_name, "stream": False},
                timeout=httpx.Timeout(600.0),  # 10 minute timeout for large models
            )
            response.raise_for_status()

            logger.info("ollama_model_pulled", model=model_name)
            return True

        except Exception as e:
            logger.error("ollama_pull_error", model=model_name, error=str(e))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
