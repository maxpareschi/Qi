"""
Adapter interfaces for database and authentication services.

This module defines the contract that all adapters must follow to be used
with the QiDbManager.
"""

import abc
from typing import Any, Generic, List, TypeVar

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
    async def get(self, collection: str, doc_id: str) -> T | None:
        """
        Retrieve data from a collection by document ID.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_all(self, collection: str) -> dict[str, T]:
        """
        Retrieve all documents from a collection.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def put(self, collection: str, doc_id: str, document: T) -> None:
        """
        Store a document in a collection.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, collection: str, doc_id: str) -> bool:
        """
        Delete a document from a collection.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def list_collections(self) -> List[str]:
        """
        List all collections in the database.
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
