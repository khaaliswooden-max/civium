"""
Common Models
=============

Base response models and utilities.

Version: 0.1.0
"""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = True
    data: T | None = None
    message: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated API response."""

    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1

    @property
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        """Check if there's a previous page."""
        return self.page > 1


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = False
    error: str
    error_code: str | None = None
    details: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HealthResponse(BaseModel):
    """Service health check response."""

    status: str = "healthy"
    service: str
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Component health
    components: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Check if all components are healthy."""
        if self.status != "healthy":
            return False
        return all(
            c.get("status") == "healthy" for c in self.components.values()
        )


class Pagination(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit for database queries."""
        return self.page_size

