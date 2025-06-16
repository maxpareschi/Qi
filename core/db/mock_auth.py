"""
Mock authentication adapter for development and testing.

This adapter simulates an authentication service with predefined users
and projects. It does not connect to any external service.
"""

import asyncio
import time
from typing import Any

from core.db.adapters import AuthenticationError, QiAuthAdapter
from core.logger import get_logger

log = get_logger(__name__)


class MockAuthAdapter(QiAuthAdapter):
    """
    Mock authentication adapter that simulates a real auth service.

    This adapter stores users and tokens in memory and does not persist
    across application restarts.
    """

    def __init__(self):
        self._users = {
            "admin": {
                "id": "user-001",
                "name": "Admin User",
                "password": "admin",  # In a real system, this would be hashed
                "roles": ["admin"],
            },
            "artist": {
                "id": "user-002",
                "name": "Test Artist",
                "password": "artist",
                "roles": ["artist"],
            },
            "guest": {
                "id": "user-003",
                "name": "Guest User",
                "password": "guest",
                "roles": ["guest"],
            },
        }

        self._projects = [
            {
                "id": "proj-001",
                "name": "Demo Project",
                "code": "DEMO",
                "description": "A demonstration project for testing",
            },
            {
                "id": "proj-002",
                "name": "Test Project",
                "code": "TEST",
                "description": "A test project for development",
            },
        ]

        # Map of active tokens to user info
        self._active_tokens: dict[str, dict[str, Any]] = {}

        log.info("MockAuthAdapter initialized with test users and projects")

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """
        Authenticate a user with the given credentials.

        Args:
            username: The user's login name
            password: The user's password

        Returns:
            User information and token

        Raises:
            AuthenticationError: If credentials are invalid
        """
        # Simulate network delay
        await asyncio.sleep(0.1)

        if username not in self._users:
            log.warning(f"Login attempt with unknown username: {username}")
            raise AuthenticationError(f"Unknown user: {username}")

        user = self._users[username]
        if user["password"] != password:
            log.warning(f"Failed login attempt for user: {username}")
            raise AuthenticationError("Invalid credentials")

        # Generate a simple token (in a real system, this would be a JWT)
        token = f"{username}-{int(time.time())}-{hash(password) % 10000:04d}"

        # Store token -> user mapping
        user_info = {
            "id": user["id"],
            "name": user["name"],
            "roles": user["roles"],
        }
        self._active_tokens[token] = user_info

        log.info(f"User {username} logged in successfully")
        return {
            "token": token,
            "user": user_info,
        }

    async def validate_token(self, token: str) -> dict[str, Any]:
        """
        Validate an authentication token.

        Args:
            token: The authentication token to validate

        Returns:
            User information if token is valid

        Raises:
            AuthenticationError: If token is invalid
        """
        # Simulate network delay
        await asyncio.sleep(0.05)

        if token not in self._active_tokens:
            log.warning(f"Invalid token validation attempt: {token}")
            raise AuthenticationError("Invalid or expired token")

        user_info = self._active_tokens[token]
        return {
            "token": token,
            "user": user_info,
        }

    async def list_projects(self, token: str) -> list[dict[str, Any]]:
        """
        list all projects accessible to the authenticated user.

        Args:
            token: Valid authentication token

        Returns:
            list of project dictionaries

        Raises:
            AuthenticationError: If token is invalid
        """
        # Validate token first
        await self.validate_token(token)

        # Simulate network delay
        await asyncio.sleep(0.2)

        # In a real system, we would filter projects by user permissions
        # For the mock, we return all projects
        return self._projects.copy()
