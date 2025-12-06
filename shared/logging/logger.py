"""
Logger Implementation
=====================

Configures structlog for structured logging with:
- JSON output in production
- Colored console output in development
- OpenTelemetry trace correlation
- Request context binding

Version: 0.1.0
"""

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog
from structlog.types import Processor


if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger


def _add_service_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add service-level context to all log entries."""
    event_dict.setdefault("service", "civium")
    event_dict.setdefault("version", "0.1.0")
    return event_dict


def _add_timestamp(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add ISO timestamp to log entries."""
    import datetime

    event_dict["timestamp"] = datetime.datetime.now(datetime.UTC).isoformat()
    return event_dict


def _censor_secrets(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Censor sensitive data in logs."""
    sensitive_keys = {
        "password",
        "api_key",
        "secret",
        "token",
        "authorization",
        "private_key",
        "credit_card",
    }

    def censor_dict(d: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, value in d.items():
            key_lower = key.lower()
            if any(s in key_lower for s in sensitive_keys):
                result[key] = "***REDACTED***"
            elif isinstance(value, dict):
                result[key] = censor_dict(value)
            else:
                result[key] = value
        return result

    return censor_dict(event_dict)


def setup_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
    service_name: str = "civium",
) -> None:
    """
    Configure structlog for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to output JSON format (True for production)
        service_name: Name of the service for context
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Disable noisy loggers
    for noisy_logger in ["httpx", "httpcore", "urllib3", "asyncio"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Build processor chain
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        _add_timestamp,
        _add_service_context,
        _censor_secrets,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_logs:
        # Production: JSON output
        shared_processors.append(structlog.processors.format_exc_info)
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        # Development: Colored console output
        shared_processors.append(structlog.dev.set_exc_info)
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.RichTracebackFormatter(
                show_locals=True,
                max_frames=10,
            ),
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Apply to root logger
    root_handler = logging.StreamHandler(sys.stdout)
    root_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(root_handler)


def get_logger(name: str | None = None) -> "BoundLogger":
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        BoundLogger: Structured logger with context binding support

    Example:
        logger = get_logger(__name__)
        logger.info("processing_request", request_id="abc123", user_id="user1")
    """
    return structlog.stdlib.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables to all subsequent logs in this async context.

    Args:
        **kwargs: Key-value pairs to add to log context

    Example:
        bind_context(request_id="abc123", user_id="user1")
        logger.info("event")  # Will include request_id and user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()
