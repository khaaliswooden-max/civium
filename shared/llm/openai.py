"""
OpenAI Provider
===============

OpenAI GPT API implementation (backup provider).

Version: 0.1.0
"""

import time
from typing import Any

import openai
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

# Pricing per 1M tokens (as of 2024)
OPENAI_PRICING = {
    "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


class OpenAIProvider(LLMProvider):
    """
    OpenAI GPT provider implementation.

    Supports GPT-4 Turbo, GPT-4, and GPT-3.5 Turbo models.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (default from settings)
            model: Model to use (default from settings)
        """
        self._api_key = api_key or settings.llm.openai.api_key.get_secret_value()
        self._model = model or settings.llm.openai.model

        if not self._api_key:
            raise ValueError("OpenAI API key not configured")

        self._client = openai.AsyncOpenAI(api_key=self._api_key)

        logger.debug("openai_provider_initialized", model=self._model)

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError)),
        stop=stop_after_attempt(settings.llm.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        before_sleep=lambda retry_state: logger.warning(
            "openai_retry",
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
        Generate a completion using OpenAI.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            stop_sequences: Stop sequences

        Returns:
            LLMResponse with generated content
        """
        start_time = time.perf_counter()

        # Convert messages to OpenAI format
        api_messages = [msg.to_dict() for msg in messages]

        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "temperature": temperature if temperature is not None else settings.llm.temperature,
        }

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        if stop_sequences:
            kwargs["stop"] = stop_sequences

        try:
            response = await self._client.chat.completions.create(**kwargs)

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract content
            content = response.choices[0].message.content or ""

            # Calculate costs
            pricing = OPENAI_PRICING.get(
                self._model,
                {"input": 10.00, "output": 30.00},
            )

            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0

            input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
            output_cost = (completion_tokens / 1_000_000) * pricing["output"]

            usage = LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                input_cost=input_cost,
                output_cost=output_cost,
                total_cost=input_cost + output_cost,
            )

            logger.debug(
                "openai_completion",
                model=self._model,
                tokens=usage.total_tokens,
                cost=usage.total_cost,
                latency_ms=round(latency_ms, 2),
            )

            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.name,
                usage=usage,
                finish_reason=response.choices[0].finish_reason,
                latency_ms=latency_ms,
            )

        except openai.BadRequestError as e:
            logger.error("openai_bad_request", error=str(e))
            raise
        except openai.AuthenticationError as e:
            logger.error("openai_auth_error", error=str(e))
            raise
        except Exception as e:
            logger.error("openai_error", error=str(e), error_type=type(e).__name__)
            raise

    async def health_check(self) -> dict[str, Any]:
        """
        Check OpenAI API health.

        Returns:
            dict with status and model info
        """
        try:
            start = time.perf_counter()

            # List models to verify API access
            models = await self._client.models.list()

            latency_ms = (time.perf_counter() - start) * 1000

            return {
                "status": "healthy",
                "provider": self.name,
                "model": self._model,
                "latency_ms": round(latency_ms, 2),
            }

        except Exception as e:
            logger.error("openai_health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "provider": self.name,
                "model": self._model,
                "error": str(e),
            }
