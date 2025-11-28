"""
Password Hashing
================

Secure password hashing using bcrypt.

Version: 0.1.0
"""

from passlib.context import CryptContext

# Configure bcrypt with default rounds
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        str: Bcrypt hash of the password
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash to verify against

    Returns:
        bool: True if password matches hash
    """
    return _pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a password hash needs to be rehashed.

    This can happen when bcrypt rounds are increased or
    the hashing algorithm is upgraded.

    Args:
        hashed_password: Existing password hash

    Returns:
        bool: True if password should be rehashed
    """
    return _pwd_context.needs_update(hashed_password)

