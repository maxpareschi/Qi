"""
Adapter interfaces for database and authentication services.

This module defines the contract that all adapters must follow to be used
with the QiDbManager.
"""

import abc
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class QiAuthAdapter(abc.ABC):
    """
    Interface for authentication adapters.

    Auth adapters handle user authentication and project/context data retrieval.
    """

    @abc.abstractmethod
    async def login(self, username: str, password: str) -> dict[str, Any]:
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

    @abc.abstractmethod
    async def validate_token(self, token: str) -> dict[str, Any]:
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

    @abc.abstractmethod
    async def list_projects(self, token: str) -> list[dict[str, Any]]:
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


class QiStorageAdapter(Generic[T], abc.ABC):
    """
    Interface for storage adapters.

    Storage adapters handle persistent data storage and retrieval.
    They are generic over the type of data they store.
    """

    @abc.abstractmethod
    async def get(self, key: str) -> T | None:
        """
        Retrieve data by key.

        Args:
            key: The unique identifier for the data

        Returns:
            The stored data, or None if not found
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def set(self, key: str, value: T) -> None:
        """
        Store data by key.

        Args:
            key: The unique identifier for the data
            value: The data to store
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete data by key.

        Args:
            key: The unique identifier for the data

        Returns:
            True if data was deleted, False if key not found
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        """
        List all keys, optionally filtered by prefix.

        Args:
            prefix: Optional key prefix to filter by

        Returns:
            List of matching keys
        """
        raise NotImplementedError


class QiFileDbAdapter(QiStorageAdapter[dict[str, Any]]):
    """
    Interface for file-based storage adapters.

    File DB adapters store structured data (dictionaries) in a file-based format
    like JSON or TOML.
    """

    @abc.abstractmethod
    async def get_settings(
        self, scope: str, addon: str | None = None
    ) -> dict[str, Any]:
        """
        Retrieve settings for a specific scope and optional addon.

        Args:
            scope: The settings scope ('bundle', 'project', 'user')
            addon: Optional addon name to filter by

        Returns:
            Dictionary of settings
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def save_settings(
        self, scope: str, settings: dict[str, Any], addon: str | None = None
    ) -> None:
        """
        Save settings for a specific scope and optional addon.

        Args:
            scope: The settings scope ('bundle', 'project', 'user')
            settings: Dictionary of settings to save
            addon: Optional addon name to filter by
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def list_bundles(self) -> list[dict[str, Any]]:
        """
        List all available bundles.

        Returns:
            List of bundle dictionaries
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_bundle(self, bundle_name: str) -> dict[str, Any] | None:
        """
        Get information about a specific bundle.

        Args:
            bundle_name: The name of the bundle

        Returns:
            Bundle information or None if not found
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_active_bundle(self) -> str:
        """
        Get the name of the currently active bundle.

        Returns:
            The name of the active bundle
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def set_active_bundle(self, bundle_name: str) -> None:
        """
        Set the active bundle.

        Args:
            bundle_name: The name of the bundle to activate

        Raises:
            ValueError: If bundle does not exist
        """
        raise NotImplementedError


# Custom exceptions
class DbAdapterError(Exception):
    """Base exception for all DB adapter errors."""

    pass


class AuthenticationError(DbAdapterError):
    """Raised when authentication fails."""

    pass


class StorageError(DbAdapterError):
    """Raised when storage operations fail."""

    pass
