"""
JWT Token Management
====================

Handles JWT token creation, validation, and decoding.

Version: 0.1.0
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel, Field

from shared.config import settings
from shared.logging import get_logger


logger = get_logger(__name__)


class TokenData(BaseModel):
    """Decoded JWT token payload."""

    sub: str = Field(..., description="Subject (user ID)")
    roles: list[str] = Field(default_factory=list, description="User roles")
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Issued at")
    token_type: str = Field(default="access", description="Token type (access/refresh)")

    # Optional claims
    email: str | None = None
    entity_id: str | None = None


class TokenPair(BaseModel):
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data (must include 'sub' for user ID)
        expires_delta: Custom expiration time (default from settings)

    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.jwt.access_token_expire_minutes)

    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.now(UTC),
            "token_type": "access",
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt.secret_key.get_secret_value(),
        algorithm=settings.jwt.algorithm,
    )

    logger.debug(
        "access_token_created",
        sub=data.get("sub"),
        expires_at=expire.isoformat(),
    )

    return encoded_jwt


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT refresh token.

    Args:
        data: Payload data (must include 'sub' for user ID)
        expires_delta: Custom expiration time (default from settings)

    Returns:
        str: Encoded JWT refresh token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.jwt.refresh_token_expire_days)

    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.now(UTC),
            "token_type": "refresh",
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt.secret_key.get_secret_value(),
        algorithm=settings.jwt.algorithm,
    )

    logger.debug(
        "refresh_token_created",
        sub=data.get("sub"),
        expires_at=expire.isoformat(),
    )

    return encoded_jwt


def create_token_pair(data: dict[str, Any]) -> TokenPair:
    """
    Create both access and refresh tokens.

    Args:
        data: Payload data (must include 'sub' for user ID)

    Returns:
        TokenPair: Access and refresh tokens
    """
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt.access_token_expire_minutes * 60,
    )


def decode_token(token: str, verify_type: str | None = None) -> TokenData | None:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string
        verify_type: Optional token type to verify ('access' or 'refresh')

    Returns:
        TokenData: Decoded token data, or None if invalid

    Raises:
        JWTError: If token is invalid (caught internally, returns None)
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key.get_secret_value(),
            algorithms=[settings.jwt.algorithm],
        )

        # Validate token type if specified
        if verify_type and payload.get("token_type") != verify_type:
            logger.warning(
                "token_type_mismatch",
                expected=verify_type,
                actual=payload.get("token_type"),
            )
            return None

        # Parse into TokenData
        return TokenData(
            sub=payload["sub"],
            roles=payload.get("roles", []),
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            iat=datetime.fromtimestamp(payload.get("iat", 0), tz=UTC),
            token_type=payload.get("token_type", "access"),
            email=payload.get("email"),
            entity_id=payload.get("entity_id"),
        )

    except JWTError as e:
        logger.warning("token_decode_failed", error=str(e))
        return None


def is_token_expired(token_data: TokenData) -> bool:
    """
    Check if a token has expired.

    Args:
        token_data: Decoded token data

    Returns:
        bool: True if expired
    """
    return datetime.now(UTC) > token_data.exp
