"""
Database Manager for Qi.

This module provides a central manager for all database operations,
coordinating between different adapters for authentication and storage.
"""

from typing import Any, Optional, TypeVar

from core.db.adapters import (
    AuthenticationError,
    QiAuthAdapter,
    QiFileDbAdapter,
)
from core.logger import get_logger

T = TypeVar("T")
log = get_logger(__name__)


class QiDbManager:
    """
    Central manager for all database operations.

    This class provides a unified interface for authentication and storage
    operations, delegating to the appropriate adapter.
    """

    def __init__(self):
        self._auth_adapter: Optional[QiAuthAdapter] = None
        self._file_adapter: Optional[QiFileDbAdapter] = None

        # Current user and token
        self._current_user: dict[str, Any] = {}
        self._current_token: Optional[str] = None
        log.info("QiDbManager created")

    # -------------------- Adapter Management -------------------- #

    def set_auth_adapter(self, adapter: QiAuthAdapter) -> None:
        """
        Set the authentication adapter.

        Args:
            adapter: An implementation of QiAuthAdapter
        """
        self._auth_adapter = adapter
        log.info(f"Auth adapter set to {adapter.__class__.__name__}")

    def set_file_adapter(self, adapter: QiFileDbAdapter) -> None:
        """
        Set the file storage adapter.

        Args:
            adapter: An implementation of QiFileDbAdapter
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

    def get_file_adapter(self) -> QiFileDbAdapter:
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

    # -------------------- Authentication -------------------- #

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
            RuntimeError: If no auth adapter is set
        """
        auth_adapter = self.get_auth_adapter()

        try:
            result = await auth_adapter.login(username, password)

            # Store the current user and token
            self._current_user = result.get("user", {})
            self._current_token = result.get("token")

            return result
        except AuthenticationError as e:
            log.warning(f"Login failed for user {username}: {e}")
            raise

    async def validate_token(self, token: Optional[str] = None) -> dict[str, Any]:
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
            result = await auth_adapter.validate_token(token_to_validate)

            # If validating the current token, update user info
            if token is None or token == self._current_token:
                self._current_user = result.get("user", {})

            return result
        except AuthenticationError as e:
            # If the current token is invalid, clear it
            if token is None or token == self._current_token:
                self._current_token = None
                self._current_user = {}

            log.warning(f"Token validation failed: {e}")
            raise

    async def list_projects(self) -> list[dict[str, Any]]:
        """
        list all projects accessible to the authenticated user.

        Returns:
            list of project dictionaries

        Raises:
            AuthenticationError: If not authenticated
            RuntimeError: If no auth adapter is set
        """
        auth_adapter = self.get_auth_adapter()

        if not self._current_token:
            raise AuthenticationError("Not authenticated")

        try:
            return await auth_adapter.list_projects(self._current_token)
        except AuthenticationError as e:
            # If the token is invalid, clear it
            self._current_token = None
            self._current_user = {}
            log.warning(f"Failed to list projects: {e}")
            raise

    def get_current_user(self) -> dict[str, Any]:
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

    def logout(self) -> None:
        """
        Log out the current user.

        This clears the current token and user information.
        """
        self._current_token = None
        self._current_user = {}
        log.info("User logged out")

    # -------------------- Settings Management -------------------- #

    async def get_settings(
        self, scope: str, addon: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Retrieve settings for a specific scope and optional addon.

        Args:
            scope: The settings scope ('bundle', 'project', 'user')
            addon: Optional addon name to filter by

        Returns:
            dictionary of settings

        Raises:
            RuntimeError: If no file adapter is set
            ValueError: If scope is invalid
        """
        file_adapter = self.get_file_adapter()
        return await file_adapter.get_settings(scope, addon)

    async def save_settings(
        self, scope: str, settings: dict[str, Any], addon: Optional[str] = None
    ) -> None:
        """
        Save settings for a specific scope and optional addon.

        Args:
            scope: The settings scope ('bundle', 'project', 'user')
            settings: dictionary of settings to save
            addon: Optional addon name to filter by

        Raises:
            RuntimeError: If no file adapter is set
            ValueError: If scope is invalid
            StorageError: If saving fails
        """
        file_adapter = self.get_file_adapter()
        await file_adapter.save_settings(scope, settings, addon)

    # -------------------- Bundle Management -------------------- #

    async def list_bundles(self) -> list[dict[str, Any]]:
        """
        list all available bundles.

        Returns:
            list of bundle dictionaries

        Raises:
            RuntimeError: If no file adapter is set
        """
        file_adapter = self.get_file_adapter()
        return await file_adapter.list_bundles()

    async def get_bundle(self, bundle_name: str) -> dict[str, Any] | None:
        """
        Get information about a specific bundle.

        Args:
            bundle_name: The name of the bundle

        Returns:
            Bundle information or None if not found

        Raises:
            RuntimeError: If no file adapter is set
        """
        file_adapter = self.get_file_adapter()
        return await file_adapter.get_bundle(bundle_name)

    async def get_active_bundle(self) -> str:
        """
        Get the name of the currently active bundle.

        Returns:
            The name of the active bundle

        Raises:
            RuntimeError: If no file adapter is set
        """
        file_adapter = self.get_file_adapter()
        return await file_adapter.get_active_bundle()

    async def set_active_bundle(self, bundle_name: str) -> None:
        """
        Set the active bundle.

        Args:
            bundle_name: The name of the bundle to activate

        Raises:
            RuntimeError: If no file adapter is set
            ValueError: If bundle does not exist
        """
        file_adapter = self.get_file_adapter()
        await file_adapter.set_active_bundle(bundle_name)

    # -------------------- General Storage -------------------- #

    async def get_data(self, key: str) -> dict[str, Any] | None:
        """
        Retrieve data by key.

        Args:
            key: The unique identifier for the data

        Returns:
            The stored data, or None if not found

        Raises:
            RuntimeError: If no file adapter is set
        """
        file_adapter = self.get_file_adapter()
        return await file_adapter.get(key)

    async def save_data(self, key: str, value: dict[str, Any]) -> None:
        """
        Store data by key.

        Args:
            key: The unique identifier for the data
            value: The data to store

        Raises:
            RuntimeError: If no file adapter is set
            StorageError: If saving fails
        """
        file_adapter = self.get_file_adapter()
        await file_adapter.set(key, value)

    async def delete_data(self, key: str) -> bool:
        """
        Delete data by key.

        Args:
            key: The unique identifier for the data

        Returns:
            True if data was deleted, False if key not found

        Raises:
            RuntimeError: If no file adapter is set
        """
        file_adapter = self.get_file_adapter()
        return await file_adapter.delete(key)
