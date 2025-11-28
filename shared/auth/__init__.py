"""
Authentication Module
=====================

JWT-based authentication and authorization for Civium services.

Features:
- JWT token generation and validation
- Password hashing with bcrypt
- Role-based access control
- FastAPI dependencies for route protection

Usage:
    from shared.auth import (
        create_access_token,
        get_current_user,
        require_roles,
        hash_password,
        verify_password,
    )
    
    # Hash password for storage
    hashed = hash_password("user_password")
    
    # Verify password
    if verify_password("user_password", hashed):
        token = create_access_token({"sub": user_id, "roles": ["user"]})
    
    # Protect routes
    @app.get("/protected")
    async def protected(user: User = Depends(get_current_user)):
        return {"user": user.email}
    
    @app.get("/admin")
    async def admin(user: User = Depends(require_roles(["admin"]))):
        return {"admin": True}
"""

from shared.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenData,
)
from shared.auth.password import hash_password, verify_password
from shared.auth.dependencies import (
    get_current_user,
    get_current_active_user,
    require_roles,
    oauth2_scheme,
)

__all__ = [
    # JWT
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "TokenData",
    # Password
    "hash_password",
    "verify_password",
    # Dependencies
    "get_current_user",
    "get_current_active_user",
    "require_roles",
    "oauth2_scheme",
]

