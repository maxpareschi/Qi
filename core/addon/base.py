import abc
from typing import Literal

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
