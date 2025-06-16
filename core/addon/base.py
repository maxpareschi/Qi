from __future__ import annotations

import abc
from typing import Literal

from core.settings.base import QiGroup

AddonRole = Literal["auth", "db", "host", "settings", "cli", "rest"]


class QiAddonBase(abc.ABC):
    """
    Abstract base class for all Qi addons.

    Addons are self-contained modules that extend Qi's functionality.
    Each addon must have a unique `name` and can optionally declare a `role`
    to provide a core service like authentication or database access.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """A unique, machine-readable name for the addon."""
        raise NotImplementedError

    @property
    def role(self) -> AddonRole | None:
        """
        The core role provided by this addon, if any.

        Core roles like 'auth' and 'db' are loaded in a special pre-load
        phase. Most addons will not have a role.
        """
        return None

    def discover(self) -> None:
        """
        Called after the addon is instantiated.

        Use this for any initial setup that doesn't depend on other addons
        or a fully running system.
        """
        pass

    @abc.abstractmethod
    def register(self) -> None:
        """
        Called to register the addon's functionality.

        This is the main entry point for an addon to register its message bus
        handlers, REST API routes, UI components, and plugins. This method is
        called after all provider addons ('auth', 'db') have been registered.
        """
        raise NotImplementedError

    def get_settings_definition(self) -> "QiGroup | None":
        """
        Optional method for an addon to define its settings schema.

        Returns:
            A QiGroup object defining the addon's settings, or None if the
            addon has no settings.
        """
        return None

    def install(self) -> None:
        """
        Optional method called after all addons have been registered.

        Use this for logic that needs to interact with other fully registered
        addons.
        """
        pass

    @abc.abstractmethod
    def close(self) -> None:
        """
        Called during application shutdown for graceful cleanup.

        Use this to unregister handlers, close connections, or save state.
        """
        raise NotImplementedError


class AddonManagerError(Exception):
    """Base exception for the Addon Manager."""


class AddonDiscoveryError(AddonManagerError):
    """Raised when an addon cannot be discovered from its path."""


class AddonLoadError(AddonManagerError):
    """Raised when an addon module fails to load or instantiate."""


class MissingProviderError(AddonManagerError):
    """Raised when a required provider addon (e.g., 'auth' or 'db') is not found."""

    def __init__(self, role: str):
        self.role = role
        super().__init__(f"Mandatory provider addon with role '{role}' not found.")


class DuplicateRoleError(AddonManagerError):
    """Raised when multiple addons are found for a unique role."""

    def __init__(self, role: str, addons: list[str]):
        self.role = role
        self.addons = addons
        super().__init__(
            f"Found multiple addons for unique role '{role}': {', '.join(addons)}"
        )
