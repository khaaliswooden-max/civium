# ADR-003: LLM Selection and Provider Strategy

## Status
**Accepted** - November 2024

## Context
Civium requires LLM capabilities for:
- Regulatory document parsing and extraction
- Requirement classification and tier assignment
- Natural language to formal logic conversion
- Compliance guidance generation

Key requirements:
- High accuracy for regulatory text
- Support for long documents (100K+ tokens)
- Cost-effective for batch processing
- Privacy considerations for sensitive data

## Decision

### Multi-Provider Strategy

| Provider | Use Case | Model |
|----------|----------|-------|
| **Primary**: Claude | Real-time parsing, high-accuracy tasks | claude-sonnet-4-20250514 |
| **Secondary**: OpenAI | Backup, embeddings | gpt-4-turbo |
| **Local**: Ollama | Batch processing, cost optimization | llama3.3:70b |

### Architecture

```python
# Strategy pattern for provider abstraction
class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[LLMMessage]) -> LLMResponse: ...

class ClaudeProvider(LLMProvider): ...
class OpenAIProvider(LLMProvider): ...
class OllamaProvider(LLMProvider): ...

# Factory with fallback
def get_llm_provider() -> LLMProvider:
    return provider based on settings.llm.provider
```

### Provider Selection Criteria

| Task | Provider | Rationale |
|------|----------|-----------|
| Real-time parsing | Claude | Best regulatory understanding |
| Batch extraction | Ollama | Zero API cost |
| Embeddings | OpenAI | Mature embedding models |
| Fallback | Any | Resilience |

## Rejected Alternatives

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Single provider | No fallback, vendor lock-in |
| Open-source only | Accuracy gap for complex regulatory text |
| Fine-tuned models | Maintenance burden, deployment complexity |

## Consequences

### Positive
- Best-in-class accuracy for primary tasks
- Cost optimization through local fallback
- No single point of failure
- Flexibility to add new providers

### Negative
- Complexity of managing multiple providers
- Prompt engineering for each provider
- Different token limits and behaviors

### Cost Analysis

| Provider | Cost (per 1M tokens) | Monthly estimate (100K docs) |
|----------|---------------------|------------------------------|
| Claude | $3/input, $15/output | ~$500 |
| GPT-4 | $10/input, $30/output | ~$1,200 |
| Ollama | Hardware only | ~$50 (GPU compute) |

## Configuration

```bash
# Environment variables
LLM_PROVIDER=claude              # Primary provider
ANTHROPIC_API_KEY=sk-...         # Claude API key
OLLAMA_HOST=http://localhost:11434  # Local Ollama
```

## Related
- Regulatory Intelligence Service
- Self-improvement feedback loops
- ADR-004: Cost tracking system (future)

