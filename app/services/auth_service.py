"""Authentication service using Supabase Auth"""

import logging
from typing import Optional, Dict, Any
from supabase import create_client, Client
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication using Supabase Auth"""

    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key,  # Use anon key for auth operations
        )

    async def register_user(
        self, email: str, password: str, full_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a new user using Supabase Auth

        Args:
            email: User email
            password: User password
            full_name: Optional full name for user metadata

        Returns:
            Dictionary containing user data and session

        Raises:
            Exception: If registration fails
        """
        try:
            user_metadata = {}
            if full_name:
                user_metadata["full_name"] = full_name

            response = self.client.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"data": user_metadata},
                }
            )

            if not response.user:
                raise ValueError("User registration failed")

            return {"user": response.user, "session": response.session}

        except Exception as e:
            logger.error(f"Error registering user: {str(e)}")
            raise

    async def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Login user using Supabase Auth

        Args:
            email: User email
            password: User password

        Returns:
            Dictionary containing user data and session with access_token

        Raises:
            Exception: If login fails
        """
        try:
            response = self.client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )

            if not response.user or not response.session:
                raise ValueError("Invalid credentials")

            return {"user": response.user, "session": response.session}

        except Exception as e:
            logger.error(f"Error logging in user: {str(e)}")
            raise

    async def get_user_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from JWT token

        Args:
            token: JWT access token

        Returns:
            User data if token is valid, None otherwise
        """
        try:
            response = self.client.auth.get_user(token)
            return response.user if response.user else None
        except Exception as e:
            logger.warning(f"Error getting user from token: {str(e)}")
            return None

    async def refresh_session(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh user session using refresh token

        Args:
            refresh_token: Refresh token

        Returns:
            New session data
        """
        try:
            response = self.client.auth.refresh_session(refresh_token)
            return {"user": response.user, "session": response.session}
        except Exception as e:
            logger.error(f"Error refreshing session: {str(e)}")
            raise

    async def logout(self, token: str) -> None:
        """
        Logout user by invalidating the session

        Args:
            token: JWT access token
        """
        try:
            # Set the session first
            self.client.auth.set_session(token, token)
            self.client.auth.sign_out()
        except Exception as e:
            logger.error(f"Error logging out: {str(e)}")
            raise
