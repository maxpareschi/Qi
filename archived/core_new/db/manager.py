# core_new/db/manager.py

"""
Database Manager for Qi.

This module provides a central manager for database operations, coordinating
between different adapters for authentication and storage.
"""

import asyncio
from typing import Any, Dict, List, Optional, TypeVar

from core_new.abc import ManagerBase
from core_new.db.adapters import QiAuthAdapter, QiStorageAdapter
from core_new.di import container
from core_new.logger import get_logger

log = get_logger("db.manager")

T = TypeVar("T")


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""

    pass


class StorageError(Exception):
    """Exception raised for storage errors."""

    pass


class AuthAdapter:
    """
    Interface for authentication adapters.

    Auth adapters handle user authentication and project/context data retrieval.
    """

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a user with the given credentials.

        Args:
            username: The user's login name
            password: The user's password

        Returns:
            A dictionary containing at minimum:
            {
                "token": str,       # Authentication token for future requests
                "user": {
                    "id": str,      # Unique user ID
                    "name": str,    # Display name
                    "roles": list,  # User roles/permissions
                }
            }

        Raises:
            AuthenticationError: If login fails
        """
        raise NotImplementedError

    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate an authentication token.

        Args:
            token: The authentication token to validate

        Returns:
            User information if token is valid (same format as login)

        Raises:
            AuthenticationError: If token is invalid or expired
        """
        raise NotImplementedError

    async def list_projects(self, token: str) -> List[Dict[str, Any]]:
        """
        List all projects accessible to the authenticated user.

        Args:
            token: Valid authentication token

        Returns:
            List of project dictionaries, each containing at minimum:
            {
                "id": str,          # Unique project ID
                "name": str,        # Display name
                "code": str,        # Project code
            }
        """
        raise NotImplementedError


class StorageAdapter:
    """
    Interface for storage adapters.

    Storage adapters handle persistent data storage and retrieval.
    """

    async def get(self, key: str) -> Any:
        """
        Retrieve data by key.

        Args:
            key: The unique identifier for the data

        Returns:
            The stored data, or None if not found
        """
        raise NotImplementedError

    async def set(self, key: str, value: Any) -> None:
        """
        Store data by key.

        Args:
            key: The unique identifier for the data
            value: The data to store
        """
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        """
        Delete data by key.

        Args:
            key: The unique identifier for the data

        Returns:
            True if data was deleted, False if key not found
        """
        raise NotImplementedError

    async def list_keys(self, prefix: str = "") -> List[str]:
        """
        List all keys, optionally filtered by prefix.

        Args:
            prefix: Optional key prefix to filter by

        Returns:
            List of matching keys
        """
        raise NotImplementedError


class DatabaseManager(ManagerBase):
    """
    Central manager for all database operations.

    This class provides a unified interface for authentication and storage
    operations, delegating to the appropriate adapter.
    """

    def __init__(self):
        """Initialize the database manager."""
        self._auth_adapter: QiAuthAdapter | None = None
        self._file_adapter: QiStorageAdapter | None = None
        self._current_user: Dict[str, Any] = {}
        self._current_token: Optional[str] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """
        Initializes the database manager.

        Adapters are expected to be set by the application after provider
        addons have been loaded.
        """
        pass

    async def start(self) -> None:
        """Starts the database manager. A no-op for this manager."""
        pass

    async def shutdown(self) -> None:
        """Shuts down the database manager. A no-op for this manager."""
        pass

    def set_auth_adapter(self, adapter: QiAuthAdapter) -> None:
        """
        Set the authentication adapter.

        Args:
            adapter: An implementation of AuthAdapter
        """
        self._auth_adapter = adapter
        log.info(f"Auth adapter set to {adapter.__class__.__name__}")

    def set_file_adapter(self, adapter: QiStorageAdapter) -> None:
        """
        Set the file storage adapter.

        Args:
            adapter: An implementation of JsonFileDbAdapter
        """
        self._file_adapter = adapter
        log.info(f"File adapter set to {adapter.__class__.__name__}")

    def get_auth_adapter(self) -> QiAuthAdapter:
        """
        Get the current authentication adapter.

        Returns:
            The current auth adapter

        Raises:
            RuntimeError: If no auth adapter is set
        """
        if not self._auth_adapter:
            raise RuntimeError("No authentication adapter is set")
        return self._auth_adapter

    def get_file_adapter(self) -> QiStorageAdapter:
        """
        Get the current file storage adapter.

        Returns:
            The current file adapter

        Raises:
            RuntimeError: If no file adapter is set
        """
        if not self._file_adapter:
            raise RuntimeError("No file storage adapter is set")
        return self._file_adapter

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a user with the given credentials.

        Args:
            username: The user's login name
            password: The user's password

        Returns:
            User information and token

        Raises:
            AuthenticationError: If credentials are invalid
            RuntimeError: If no auth adapter is set
        """
        auth_adapter = self.get_auth_adapter()

        try:
            async with self._lock:
                result = await auth_adapter.login(username, password)

                # Store the current user and token
                self._current_user = result.get("user", {})
                self._current_token = result.get("token")

            return result
        except Exception as e:
            log.warning(f"Login failed for user {username}: {e}")
            raise AuthenticationError(str(e))

    async def validate_token(self, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate an authentication token.

        Args:
            token: The token to validate, or None to use the current token

        Returns:
            User information if token is valid

        Raises:
            AuthenticationError: If token is invalid
            RuntimeError: If no auth adapter is set or no token is available
        """
        auth_adapter = self.get_auth_adapter()

        # Use the provided token or fall back to the current token
        token_to_validate = token or self._current_token

        if not token_to_validate:
            raise AuthenticationError("No authentication token available")

        try:
            async with self._lock:
                result = await auth_adapter.validate_token(token_to_validate)

                # If validating the current token, update user info
                if token is None or token == self._current_token:
                    self._current_user = result.get("user", {})

            return result
        except Exception as e:
            # If the current token is invalid, clear it
            if token is None or token == self._current_token:
                async with self._lock:
                    self._current_token = None
                    self._current_user = {}

            log.warning(f"Token validation failed: {e}")
            raise AuthenticationError(str(e))

    async def list_projects(self) -> List[Dict[str, Any]]:
        """
        List all projects accessible to the authenticated user.

        Returns:
            List of project dictionaries

        Raises:
            AuthenticationError: If not authenticated
            RuntimeError: If no auth adapter is set
        """
        auth_adapter = self.get_auth_adapter()

        if not self._current_token:
            raise AuthenticationError("Not authenticated")

        try:
            return await auth_adapter.list_projects(self._current_token)
        except Exception as e:
            # If the token is invalid, clear it
            async with self._lock:
                self._current_token = None
                self._current_user = {}
            log.warning(f"Failed to list projects: {e}")
            raise AuthenticationError(str(e))

    def get_current_user(self) -> Dict[str, Any]:
        """
        Get information about the currently authenticated user.

        Returns:
            User information, or empty dict if not authenticated
        """
        return self._current_user.copy()

    def get_current_token(self) -> Optional[str]:
        """
        Get the current authentication token.

        Returns:
            The current token, or None if not authenticated
        """
        return self._current_token

    def is_authenticated(self) -> bool:
        """
        Check if a user is currently authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        return bool(self._current_token and self._current_user)

    async def logout(self) -> None:
        """
        Log out the current user.

        This clears the current token and user information.
        """
        async with self._lock:
            self._current_token = None
            self._current_user = {}
        log.info("User logged out")

    async def get_settings(self, scope: str) -> dict[str, Any]:
        """
        Retrieve settings for a specific scope.

        Args:
            scope: The settings scope ('bundle', 'project', 'user')

        Returns:
            A dictionary of settings.

        Raises:
            RuntimeError: If no file adapter is set.
            ValueError: If the scope is invalid.
        """
        if scope not in ("bundle", "project", "user"):
            raise ValueError(f"Invalid settings scope: {scope}")

        file_adapter = self.get_file_adapter()
        # Get all documents in the settings collection for this scope
        settings_collection = f"settings_{scope}"
        try:
            return await file_adapter.get_all(settings_collection)
        except Exception as e:
            log.error(f"Error retrieving settings for scope '{scope}': {e}")
            return {}

    async def save_settings(self, scope: str, settings: dict[str, Any]) -> None:
        """
        Save settings for a specific scope.

        Args:
            scope: The settings scope ('bundle', 'project', 'user').
            settings: A dictionary of settings to save.

        Raises:
            RuntimeError: If no file adapter is set.
            ValueError: If the scope is invalid.
        """
        if scope not in ("bundle", "project", "user"):
            raise ValueError(f"Invalid settings scope: {scope}")

        file_adapter = self.get_file_adapter()
        settings_collection = f"settings_{scope}"

        # For each key in settings, save as a separate document
        for key, value in settings.items():
            await file_adapter.put(settings_collection, key, value)
            log.debug(f"Saved setting '{key}' in scope '{scope}'")

    async def get_data(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a generic JSON data object by its key.

        Args:
            collection: The collection name (e.g., 'settings')
            doc_id: The unique identifier for the document in the collection

        Returns:
            The stored data, or None if not found

        Raises:
            RuntimeError: If no file adapter is set
        """
        file_adapter = self.get_file_adapter()
        return await file_adapter.get(collection, doc_id)

    async def save_data(
        self, collection: str, doc_id: str, value: Dict[str, Any]
    ) -> None:
        """
        Save a generic JSON data object by its key.

        Args:
            collection: The collection name
            doc_id: The unique identifier for the document
            value: The data to store

        Raises:
            RuntimeError: If no file adapter is set
            StorageError: If saving fails
        """
        file_adapter = self.get_file_adapter()
        await file_adapter.put(collection, doc_id, value)

    async def delete_data(self, collection: str, doc_id: str) -> bool:
        """
        Delete a generic JSON data object by its key.

        Args:
            collection: The collection name
            doc_id: The unique identifier for the document

        Returns:
            True if data was deleted, False if key not found

        Raises:
            RuntimeError: If no file adapter is set
        """
        file_adapter = self.get_file_adapter()
        return await file_adapter.delete(collection, doc_id)


# Create a global database manager instance
db_manager = DatabaseManager()

# Register the database manager as a singleton service
container.register_instance("db_manager", db_manager)
