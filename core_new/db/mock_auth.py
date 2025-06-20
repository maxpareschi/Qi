"""
Mock Authentication Adapter for Qi.

This module provides a mock authentication adapter for development and testing.
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from core_new.db.adapters import AuthenticationError, QiAuthAdapter
from core_new.logger import get_logger

log = get_logger("db.mock_auth")


class MockAuthAdapter(QiAuthAdapter):
    """
    Mock authentication adapter for development and testing.

    This adapter provides a simple in-memory authentication system with
    persistence to a JSON file.
    """

    def __init__(self, users_file: Optional[str] = None):
        """
        Initialize the adapter.

        Args:
            users_file: Path to the users file. If None, no persistence is used.
        """
        self._users_file = users_file
        self._users: Dict[str, Dict] = {}
        self._sessions: Dict[str, str] = {}  # token -> user_id
        self._lock = asyncio.Lock()
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

        # Load users from file if provided
        if users_file:
            self._load_users()

        # Create a default admin user if no users exist
        if not self._users:
            self._create_default_user()

    def _load_users(self) -> None:
        """Load users from the users file."""
        if not self._users_file:
            return

        users_path = Path(self._users_file)
        if not users_path.exists():
            log.info(f"Users file not found: {users_path}")
            return

        try:
            with open(users_path, "r", encoding="utf-8") as f:
                self._users = json.load(f)
                log.info(f"Loaded {len(self._users)} users from {users_path}")
        except Exception as e:
            log.error(f"Error loading users from {users_path}: {e}")

    def _save_users(self) -> None:
        """Save users to the users file."""
        if not self._users_file:
            return

        users_path = Path(self._users_file)
        users_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(users_path, "w", encoding="utf-8") as f:
                json.dump(self._users, f, indent=2)
                log.info(f"Saved {len(self._users)} users to {users_path}")
        except Exception as e:
            log.error(f"Error saving users to {users_path}: {e}")

    def _create_default_user(self) -> None:
        """Create a default admin user."""
        user_id = str(uuid.uuid4())
        self._users[user_id] = {
            "id": user_id,
            "name": "Admin User",
            "email": "admin@example.com",
            "username": "admin",
            "password": "admin",  # In a real system, this would be hashed
            "roles": ["admin"],
        }
        log.info("Created default admin user")
        self._save_users()

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """
        Authenticate a user with username and password.

        Args:
            username: The username to authenticate.
            password: The password to authenticate.

        Returns:
            The user data if authentication succeeds, None otherwise.
        """
        async with self._lock:
            for user in self._users.values():
                if user["username"] == username and user["password"] == password:
                    # Create a session token
                    token = str(uuid.uuid4())
                    self._sessions[token] = user["id"]

                    # Return user data without sensitive fields
                    user_data = {
                        "id": user["id"],
                        "name": user["name"],
                        "roles": user["roles"],
                    }

                    log.info(f"User authenticated: {username}")
                    return {"token": token, "user": user_data}

        log.warning(f"Authentication failed for user: {username}")
        raise AuthenticationError("Invalid credentials")

    async def validate_token(self, token: str) -> dict[str, Any]:
        """
        Validate a session token.

        Args:
            token: The session token to validate.

        Returns:
            The user data if the token is valid, None otherwise.
        """
        async with self._lock:
            user_id = self._sessions.get(token)
            if not user_id:
                raise AuthenticationError("Invalid or expired token")

            user = self._users.get(user_id)
            if not user:
                # Clean up invalid session
                self._sessions.pop(token, None)
                raise AuthenticationError("Invalid or expired token")

            # Return user data without sensitive fields
            user_data = {
                "id": user["id"],
                "name": user["name"],
                "roles": user["roles"],
            }
            return {"token": token, "user": user_data}

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

        # In a real system, we would filter projects by user permissions
        # For the mock, we return all projects
        return self._projects.copy()

    async def logout(self, token: str) -> bool:
        """
        Logout a user by invalidating their session token.

        Args:
            token: The session token to invalidate.

        Returns:
            True if the token was invalidated, False otherwise.
        """
        async with self._lock:
            if token in self._sessions:
                self._sessions.pop(token)
                log.info(f"User logged out: {token}")
                return True

        return False

    async def create_user(
        self,
        username: str,
        password: str,
        name: str,
        email: str,
        roles: List[str] = None,
    ) -> Optional[Dict]:
        """
        Create a new user.

        Args:
            username: The username for the new user.
            password: The password for the new user.
            name: The name of the new user.
            email: The email of the new user.
            roles: The roles for the new user.

        Returns:
            The user data if creation succeeds, None if the username already exists.
        """
        if not roles:
            roles = ["user"]

        async with self._lock:
            # Check if username already exists
            for user in self._users.values():
                if user["username"] == username:
                    log.warning(
                        f"User creation failed: username already exists: {username}"
                    )
                    return None

            # Create the user
            user_id = str(uuid.uuid4())
            self._users[user_id] = {
                "id": user_id,
                "name": name,
                "email": email,
                "username": username,
                "password": password,  # In a real system, this would be hashed
                "roles": roles,
            }

            # Save users
            self._save_users()

            # Return user data without sensitive fields
            user_data = self._users[user_id].copy()
            user_data.pop("password", None)

            log.info(f"User created: {username}")
            return user_data
