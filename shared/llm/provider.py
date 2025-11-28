"""
LLM Provider Base
=================

Abstract base class and common models for LLM providers.

Version: 0.1.0
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from shared.config import settings, LLMProvider as LLMProviderEnum
from shared.logging import get_logger

logger = get_logger(__name__)


class MessageRole(str, Enum):
    """Message role in conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class LLMMessage(BaseModel):
    """A message in the conversation."""

    role: MessageRole | Literal["system", "user", "assistant"]
    content: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dict for API calls."""
        role_str = self.role.value if isinstance(self.role, MessageRole) else self.role
        return {"role": role_str, "content": self.content}


class LLMUsage(BaseModel):
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Cost tracking (in USD)
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0


class LLMResponse(BaseModel):
    """Response from LLM provider."""

    content: str = Field(..., description="Generated text content")
    model: str = Field(..., description="Model used for generation")
    provider: str = Field(..., description="Provider name")
    usage: LLMUsage = Field(default_factory=LLMUsage)
    finish_reason: str | None = None

    # Additional metadata
    latency_ms: float = 0.0
    raw_response: dict[str, Any] | None = None


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Implements the Strategy pattern for swappable LLM backends.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop_sequences: list[str] | None = None,
    ) -> LLMResponse:
        """
        Generate a completion for the given messages.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            stop_sequences: Stop generation at these sequences

        Returns:
            LLMResponse with generated content
        """
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """
        Check provider health.

        Returns:
            dict with status and provider info
        """
        ...

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Simple text generation helper.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional arguments for complete()

        Returns:
            Generated text content
        """
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))

        response = await self.complete(messages, **kwargs)
        return response.content

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate JSON output.

        Args:
            prompt: User prompt requesting JSON
            system_prompt: Optional system prompt
            **kwargs: Additional arguments

        Returns:
            Parsed JSON dict
        """
        import json

        # Add JSON instruction to system prompt
        json_system = (system_prompt or "") + (
            "\n\nRespond ONLY with valid JSON. No markdown, no explanation."
        )

        text = await self.generate_text(prompt, system_prompt=json_system.strip(), **kwargs)

        # Clean potential markdown formatting
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        return json.loads(text)


# Global provider instance
_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """
    Get the configured LLM provider instance.

    Uses the provider specified in settings.llm.provider.
    Creates and caches the instance on first call.

    Returns:
        LLMProvider instance
    """
    global _provider

    if _provider is None:
        provider_type = settings.llm.provider

        if provider_type == LLMProviderEnum.CLAUDE:
            from shared.llm.claude import ClaudeProvider

            _provider = ClaudeProvider()
        elif provider_type == LLMProviderEnum.OPENAI:
            from shared.llm.openai import OpenAIProvider

            _provider = OpenAIProvider()
        elif provider_type == LLMProviderEnum.OLLAMA:
            from shared.llm.ollama import OllamaProvider

            _provider = OllamaProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider_type}")

        logger.info(
            "llm_provider_initialized",
            provider=_provider.name,
            model=_provider.model,
        )

    return _provider


def set_llm_provider(provider: LLMProvider) -> None:
    """
    Set a custom LLM provider.

    Useful for testing or custom implementations.

    Args:
        provider: LLMProvider instance to use
    """
    global _provider
    _provider = provider
    logger.info(
        "llm_provider_set",
        provider=provider.name,
        model=provider.model,
    )


def reset_llm_provider() -> None:
    """Reset the provider to be re-initialized on next access."""
    global _provider
    _provider = None

