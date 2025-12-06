"""
Monitoring Service Routes
=========================

API route handlers for the monitoring service.
"""

from services.monitoring.routes import alerts, events, metrics, streams


__all__ = ["alerts", "events", "metrics", "streams"]
