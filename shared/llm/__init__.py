"""
LLM Provider Module
===================

Abstraction layer for multiple LLM providers.

Supported providers:
- Anthropic Claude (primary)
- OpenAI GPT (backup)
- Ollama (local, cost optimization)

Usage:
    from shared.llm import get_llm_provider, LLMMessage
    
    provider = get_llm_provider()
    
    response = await provider.complete(
        messages=[
            LLMMessage(role="system", content="You are a regulatory expert."),
            LLMMessage(role="user", content="Explain GDPR Article 6."),
        ]
    )
    print(response.content)
"""

from shared.llm.provider import (
    LLMProvider,
    LLMMessage,
    LLMResponse,
    LLMUsage,
    get_llm_provider,
    set_llm_provider,
)
from shared.llm.claude import ClaudeProvider
from shared.llm.ollama import OllamaProvider

__all__ = [
    # Base
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "LLMUsage",
    "get_llm_provider",
    "set_llm_provider",
    # Providers
    "ClaudeProvider",
    "OllamaProvider",
]

