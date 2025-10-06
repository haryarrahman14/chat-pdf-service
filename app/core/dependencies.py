"""FastAPI dependencies for authentication using Supabase Auth"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService

# Security scheme for JWT bearer token
security = HTTPBearer()
auth_service = AuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependency to extract and validate user from Supabase JWT token

    Args:
        credentials: HTTP bearer token credentials

    Returns:
        User object from Supabase Auth

    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    user = await auth_service.get_user_from_token(token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_id(current_user: dict = Depends(get_current_user)) -> str:
    """
    Dependency to extract user_id from Supabase Auth user

    Args:
        current_user: Current user object from get_current_user

    Returns:
        User ID string
    """
    return current_user.id
