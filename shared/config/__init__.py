"""
Configuration Module
====================

Centralized configuration management using Pydantic Settings.
Loads from environment variables with type validation and defaults.

Usage:
    from shared.config import settings

    print(settings.environment)
    print(settings.postgres.host)
"""

from shared.config.settings import (
    Settings,
    get_settings,
    Environment,
    LogLevel,
    LLMProvider,
    BlockchainMode,
)


# Global settings instance (singleton)
settings = get_settings()

__all__ = [
    "Settings",
    "get_settings",
    "settings",
    "Environment",
    "LogLevel",
    "LLMProvider",
    "BlockchainMode",
]
