"""
Unit tests for authentication module.
"""

import pytest
from datetime import timedelta

from shared.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from shared.auth.jwt import TokenData


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_hash(self) -> None:
        """Test that hash_password returns a bcrypt hash."""
        password = "test_password_123"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")
        assert len(hashed) == 60

    def test_verify_password_correct(self) -> None:
        """Test that verify_password returns True for correct password."""
        password = "correct_password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self) -> None:
        """Test that verify_password returns False for incorrect password."""
        password = "correct_password"
        hashed = hash_password(password)

        assert verify_password("wrong_password", hashed) is False

    def test_different_passwords_different_hashes(self) -> None:
        """Test that different passwords produce different hashes."""
        hash1 = hash_password("password1")
        hash2 = hash_password("password2")

        assert hash1 != hash2


class TestJWTTokens:
    """Tests for JWT token functions."""

    def test_create_access_token(self) -> None:
        """Test access token creation."""
        data = {"sub": "user123", "roles": ["user"]}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 50

    def test_decode_access_token(self) -> None:
        """Test access token decoding."""
        data = {"sub": "user123", "roles": ["admin"], "email": "test@example.com"}
        token = create_access_token(data)

        decoded = decode_token(token, verify_type="access")

        assert decoded is not None
        assert decoded.sub == "user123"
        assert "admin" in decoded.roles
        assert decoded.email == "test@example.com"
        assert decoded.token_type == "access"

    def test_create_refresh_token(self) -> None:
        """Test refresh token creation."""
        data = {"sub": "user123"}
        token = create_refresh_token(data)

        decoded = decode_token(token, verify_type="refresh")

        assert decoded is not None
        assert decoded.sub == "user123"
        assert decoded.token_type == "refresh"

    def test_decode_wrong_token_type(self) -> None:
        """Test that decoding with wrong type returns None."""
        data = {"sub": "user123"}
        access_token = create_access_token(data)

        # Try to decode access token as refresh token
        decoded = decode_token(access_token, verify_type="refresh")

        assert decoded is None

    def test_decode_invalid_token(self) -> None:
        """Test that invalid token returns None."""
        decoded = decode_token("invalid.token.string")
        assert decoded is None

    def test_token_with_custom_expiry(self) -> None:
        """Test token with custom expiration."""
        data = {"sub": "user123"}
        token = create_access_token(data, expires_delta=timedelta(minutes=5))

        decoded = decode_token(token)
        assert decoded is not None


class TestTokenData:
    """Tests for TokenData model."""

    def test_token_data_required_fields(self) -> None:
        """Test TokenData requires sub and exp."""
        from datetime import datetime, UTC

        token_data = TokenData(
            sub="user123",
            exp=datetime.now(UTC),
        )

        assert token_data.sub == "user123"
        assert token_data.roles == []
        assert token_data.token_type == "access"

    def test_token_data_all_fields(self) -> None:
        """Test TokenData with all fields."""
        from datetime import datetime, UTC

        token_data = TokenData(
            sub="user123",
            exp=datetime.now(UTC),
            roles=["admin", "user"],
            email="test@example.com",
            entity_id="entity456",
            token_type="refresh",
        )

        assert token_data.email == "test@example.com"
        assert token_data.entity_id == "entity456"
        assert "admin" in token_data.roles

