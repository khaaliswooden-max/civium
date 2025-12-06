"""
FastAPI Authentication Dependencies
===================================

Dependency injection for route protection.

Version: 0.1.0
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from shared.auth.jwt import decode_token
from shared.logging import get_logger


logger = get_logger(__name__)

# OAuth2 scheme for token extraction from Authorization header
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/token",
    auto_error=False,
)


class User(BaseModel):
    """Authenticated user model for dependency injection."""

    id: str = Field(..., description="User ID")
    email: str | None = Field(default=None, description="User email")
    roles: list[str] = Field(default_factory=list, description="User roles")
    entity_id: str | None = Field(default=None, description="Associated entity ID")
    is_active: bool = Field(default=True, description="Whether user is active")


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    """
    Extract and validate user from JWT token.

    Args:
        token: JWT token from Authorization header

    Returns:
        User: Authenticated user

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        logger.warning("auth_token_missing")
        raise credentials_exception

    token_data = decode_token(token, verify_type="access")

    if token_data is None:
        logger.warning("auth_token_invalid")
        raise credentials_exception

    logger.debug("user_authenticated", user_id=token_data.sub)

    return User(
        id=token_data.sub,
        email=token_data.email,
        roles=token_data.roles,
        entity_id=token_data.entity_id,
    )


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Ensure the current user is active.

    Args:
        current_user: User from get_current_user dependency

    Returns:
        User: Active user

    Raises:
        HTTPException: 403 if user is inactive
    """
    if not current_user.is_active:
        logger.warning("inactive_user_access_attempt", user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


def require_roles(
    required_roles: list[str],
    require_all: bool = False,
) -> Callable[[User], User]:
    """
    Create a dependency that requires specific roles.

    Args:
        required_roles: List of role names required
        require_all: If True, user must have ALL roles. If False, ANY role suffices.

    Returns:
        Dependency function

    Usage:
        @app.get("/admin")
        async def admin_only(user: User = Depends(require_roles(["admin"]))):
            ...
    """

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        user_roles = set(current_user.roles)
        required = set(required_roles)

        if require_all:
            has_roles = required.issubset(user_roles)
        else:
            has_roles = bool(required.intersection(user_roles))

        if not has_roles:
            logger.warning(
                "insufficient_roles",
                user_id=current_user.id,
                user_roles=list(user_roles),
                required_roles=required_roles,
                require_all=require_all,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return role_checker


# Common role dependencies
require_admin = require_roles(["admin"])
require_assessor = require_roles(["assessor", "admin"])
require_regulator = require_roles(["regulator", "admin"])


class APIKeyUser(BaseModel):
    """User authenticated via API key."""

    id: str
    key_id: str
    scopes: list[str]
    entity_id: str | None = None


async def get_api_key_user(
    api_key: Annotated[str | None, Depends(oauth2_scheme)],
) -> APIKeyUser | None:
    """
    Validate API key and return associated user.

    This is a placeholder for API key authentication.
    Actual implementation requires database lookup.

    Args:
        api_key: API key from Authorization header

    Returns:
        APIKeyUser if valid, None otherwise
    """
    # TODO: Implement API key lookup from database
    # This is a placeholder that always returns None
    return None
