"""
Claude Provider
===============

Anthropic Claude API implementation.

Version: 0.1.0
"""

import time
from typing import Any

import anthropic
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
CLAUDE_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}


class ClaudeProvider(LLMProvider):
    """
    Anthropic Claude provider implementation.

    Supports Claude 3.5 Sonnet, Opus, and Haiku models.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """
        Initialize Claude provider.

        Args:
            api_key: Anthropic API key (default from settings)
            model: Model to use (default from settings)
        """
        self._api_key = api_key or settings.llm.claude.api_key.get_secret_value()
        self._model = model or settings.llm.claude.model
        self._max_tokens = settings.llm.claude.max_tokens

        if not self._api_key:
            raise ValueError("Anthropic API key not configured")

        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

        logger.debug("claude_provider_initialized", model=self._model)

    @property
    def name(self) -> str:
        return "claude"

    @property
    def model(self) -> str:
        return self._model

    @retry(
        retry=retry_if_exception_type(
            (anthropic.RateLimitError, anthropic.APIConnectionError)
        ),
        stop=stop_after_attempt(settings.llm.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        before_sleep=lambda retry_state: logger.warning(
            "claude_retry",
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep,  # type: ignore[union-attr]
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
        Generate a completion using Claude.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature (default from settings)
            max_tokens: Max tokens to generate (default from settings)
            stop_sequences: Optional stop sequences

        Returns:
            LLMResponse with generated content
        """
        start_time = time.perf_counter()

        # Extract system message if present
        system_message = None
        api_messages = []

        for msg in messages:
            msg_dict = msg.to_dict()
            if msg_dict["role"] == "system":
                system_message = msg_dict["content"]
            else:
                api_messages.append(msg_dict)

        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": temperature if temperature is not None else settings.llm.temperature,
        }

        if system_message:
            kwargs["system"] = system_message

        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences

        try:
            response = await self._client.messages.create(**kwargs)

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract content
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            # Calculate costs
            pricing = CLAUDE_PRICING.get(
                self._model,
                {"input": 3.00, "output": 15.00},
            )
            input_cost = (response.usage.input_tokens / 1_000_000) * pricing["input"]
            output_cost = (response.usage.output_tokens / 1_000_000) * pricing["output"]

            usage = LLMUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                input_cost=input_cost,
                output_cost=output_cost,
                total_cost=input_cost + output_cost,
            )

            logger.debug(
                "claude_completion",
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
                finish_reason=response.stop_reason,
                latency_ms=latency_ms,
            )

        except anthropic.BadRequestError as e:
            logger.error("claude_bad_request", error=str(e))
            raise
        except anthropic.AuthenticationError as e:
            logger.error("claude_auth_error", error=str(e))
            raise
        except Exception as e:
            logger.error("claude_error", error=str(e), error_type=type(e).__name__)
            raise

    async def health_check(self) -> dict[str, Any]:
        """
        Check Claude API health.

        Returns:
            dict with status and model info
        """
        try:
            start = time.perf_counter()

            # Simple completion to verify API access
            response = await self._client.messages.create(
                model=self._model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )

            latency_ms = (time.perf_counter() - start) * 1000

            return {
                "status": "healthy",
                "provider": self.name,
                "model": self._model,
                "latency_ms": round(latency_ms, 2),
            }

        except Exception as e:
            logger.error("claude_health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "provider": self.name,
                "model": self._model,
                "error": str(e),
            }

    async def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        # Use anthropic's token counting
        return await self._client.count_tokens(text)

