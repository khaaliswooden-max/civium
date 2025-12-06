"""
Logging Module
==============

Structured logging using structlog with JSON output for production
and colored console output for development.

Usage:
    from shared.logging import get_logger, setup_logging

    # Setup at application start
    setup_logging()

    # Get logger for a module
    logger = get_logger(__name__)

    # Log with context
    logger.info("user_login", user_id="123", ip_address="192.168.1.1")
    logger.error("database_error", error=str(e), query=query)
"""

from shared.logging.logger import get_logger, setup_logging


__all__ = [
    "get_logger",
    "setup_logging",
]
