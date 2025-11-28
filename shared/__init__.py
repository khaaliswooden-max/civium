"""
CIVIUM Shared Library
=====================

Common utilities, configurations, and abstractions shared across all Civium services.

Modules:
    - config: Configuration management with Pydantic Settings
    - logging: Structured logging with structlog
    - auth: JWT authentication and authorization
    - database: Database client abstractions
    - llm: LLM provider abstraction (Claude, Ollama)
    - blockchain: Blockchain interface (mock/testnet/mainnet)
    - models: Shared Pydantic models

Version: 0.1.0
"""

__version__ = "0.1.0"
__author__ = "Civium Team"

from shared.config import settings
from shared.logging import get_logger, setup_logging

__all__ = [
    "settings",
    "get_logger",
    "setup_logging",
    "__version__",
]

