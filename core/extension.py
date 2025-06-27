# core/extension.py

"""
Extension module.

This module provides the base class for extensions, the ExtensionManager
that handles discovery, loading, and lifecycle management of extensions,
and the discovery functions for finding and loading extensions.
"""

import asyncio
import importlib.util
import inspect
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.config import QiLaunchConfig
from core.logger import get_logger

log = get_logger(__name__)


class ExtensionDiscoveryError(Exception):
    """Raised when extension discovery fails."""

    pass


class ExtensionLoadError(Exception):
    """Raised when extension loading fails."""

    pass


class QiExtensionBase(ABC):
    """
    Abstract base class for all Qi extensions.

    Extensions must implement the lifecycle methods to integrate properly
    with the Qi application framework.
    """

    @abstractmethod
    def discover(self):
        """
        Discovery phase - called when extension is first loaded.
        Use this for one-time setup that doesn't depend on other services.
        """
        pass

    @abstractmethod
    def register(self):
        """
        Registration phase - called after all extensions are loaded.
        Use this to register services, handlers, or other functionality.
        """
        pass

    @abstractmethod
    def initialize(self):
        """
        Initialization phase - called when the application starts.
        Use this for initialization that depends on all extensions being loaded.
        """
        pass

    @abstractmethod
    def close(self):
        """
        Cleanup phase - called during application shutdown.
        Use this to cleanup resources, save state, etc.
        """
        pass

    def extend_rest_api(self) -> list:
        """Override to provide REST API extensions."""
        return []

    def extend_cli(self) -> list:
        """Override to provide CLI extensions."""
        return []

    def extend_gui(self) -> list:
        """Override to provide GUI extensions."""
        return []


def discover_extension_directories(search_paths: list[str | Path]) -> dict[str, Path]:
    """
    Scans specified directories for valid extension subdirectories.

    A valid extension directory must contain an extension.py file.

    Args:
        search_paths: List of paths to directories containing extensions

    Returns:
        Dictionary mapping extension directory name to its absolute Path
    """
    discovered = {}

    for path_str in search_paths:
        path = Path(path_str)
        if not path.is_dir():
            log.warning(f"Extension search path does not exist: {path_str}")
            continue

        log.debug(f"Scanning for extensions in: {path}")

        for child in path.iterdir():
            if not child.is_dir():
                continue

            # Look for extension.py file
            extension_file = child / "extension.py"
            if not extension_file.is_file():
                continue

            extension_name = child.name

            if extension_name in discovered:
                log.warning(
                    f"Duplicate extension '{extension_name}' found at {child}. "
                    f"Using existing one at {discovered[extension_name]}"
                )
                continue

            discovered[extension_name] = child.resolve()
            log.debug(f"Discovered extension: {extension_name} at {child}")

    return discovered


def load_extension_from_path(
    extension_name: str, extension_path: Path
) -> QiExtensionBase:
    """
    Dynamically loads and instantiates an extension from its directory path.

    Args:
        extension_name: Name of the extension (typically directory name)
        extension_path: Absolute path to the extension's directory

    Returns:
        Instantiated extension object

    Raises:
        ExtensionLoadError: If extension cannot be loaded or instantiated
    """
    extension_file = extension_path / "extension.py"
    if not extension_file.is_file():
        raise ExtensionDiscoveryError(f"Extension file not found: {extension_file}")

    # Add extension's parent directory to sys.path for relative imports
    parent_dir = str(extension_path.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    module_name = f"{extension_name}.extension"

    try:
        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, extension_file)
        if not spec or not spec.loader:
            raise ImportError("Could not create module spec")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    except Exception as e:
        raise ExtensionLoadError(
            f"Failed to import extension '{extension_name}': {e}"
        ) from e

    # Find QiExtensionBase subclass in the module
    extension_classes = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, QiExtensionBase)
            and obj is not QiExtensionBase
            and obj.__module__ == module_name
        ):
            extension_classes.append(obj)

    if not extension_classes:
        raise ExtensionLoadError(
            f"No QiExtensionBase subclass found in '{extension_name}/extension.py'"
        )

    if len(extension_classes) > 1:
        log.warning(
            f"Multiple extension classes found in '{extension_name}', using first one: "
            f"{extension_classes[0].__name__}"
        )

    extension_class = extension_classes[0]

    try:
        # Instantiate the extension
        instance = extension_class()
        log.debug(f"Loaded extension class: {extension_class.__name__}")
        return instance

    except Exception as e:
        raise ExtensionLoadError(
            f"Failed to instantiate extension '{extension_name}': {e}"
        ) from e


def validate_extension(extension: QiExtensionBase, expected_name: str) -> None:
    """
    Validates that an extension meets basic requirements.

    Args:
        extension: The extension instance to validate
        expected_name: Expected extension name (from directory)

    Raises:
        ExtensionLoadError: If validation fails
    """
    # Validate required methods exist
    required_methods = ["discover", "register", "initialize", "close"]
    for method_name in required_methods:
        if not hasattr(extension, method_name):
            raise ExtensionLoadError(
                f"Extension missing required method: {method_name}"
            )

    # Validate extension has basic attributes
    if not hasattr(extension, "__class__"):
        raise ExtensionLoadError("Extension must be a class instance")

    log.debug(f"Extension '{expected_name}' passed validation")


class ExtensionManager:
    """
    Manages the lifecycle of extensions.

    This manager handles:
    - Discovery of extensions from configured paths
    - Loading and validation of extension modules
    - Extension lifecycle (discover → register → initialize → close)
    - Integration with Hub for dependency injection
    """

    def __init__(self, hub: Any, config: QiLaunchConfig):
        """
        Initialize the extension manager.

        Args:
            hub: The Hub instance for dependency injection
            config: Launch configuration
        """
        self.hub = hub
        self.config = config
        self._extensions: dict[str, QiExtensionBase] = {}
        self._failed_extensions: dict[str, Exception] = {}
        self._extension_errors: dict[str, Exception] = {}

    async def discover_and_load_extensions(self) -> None:
        """
        Discover and load all extensions from configured search paths.
        """
        search_paths = self.config.extensions.search_dirs
        log.info(f"Discovering extensions from paths: {search_paths}")

        # Discover extension directories
        discovered = discover_extension_directories(search_paths)
        log.info(f"Discovered {len(discovered)} extensions: {list(discovered.keys())}")

        # Load each extension
        for name, path in discovered.items():
            try:
                await self._load_extension(name, path)
            except Exception as e:
                log.error(f"Failed to load extension '{name}': {e}")
                self._failed_extensions[name] = e

        successful_count = len(self._extensions)
        failed_count = len(self._failed_extensions)
        log.info(
            f"Extension loading complete: {successful_count} loaded, {failed_count} failed"
        )

    async def _load_extension(self, name: str, path: Path) -> None:
        """
        Load a single extension from its path.

        Args:
            name: Extension name
            path: Path to extension directory
        """
        log.debug(f"Loading extension '{name}' from {path}")

        try:
            # Load the extension module
            extension = load_extension_from_path(name, path)

            # Validate the extension
            validate_extension(extension, name)

            # Store the extension
            self._extensions[name] = extension

            # Register extension with Hub for dependency injection
            self.hub.register_extension(extension)

            log.info(f"Successfully loaded extension: {name}")

        except Exception as e:
            raise ExtensionLoadError(f"Failed to load extension '{name}': {e}") from e

    async def initialize_extensions(self) -> None:
        """
        Run the discover and register lifecycle phases for all loaded extensions.
        """
        if not self._extensions:
            log.info("No extensions to initialize")
            return

        log.info("Running extension discovery phase...")
        await self._run_lifecycle_phase("discover")

        log.info("Running extension registration phase...")
        await self._run_lifecycle_phase("register")

        log.info("Extension initialization complete")

    async def start_extensions(self) -> None:
        """
        Run the initialize lifecycle phase for all extensions.
        """
        if not self._extensions:
            log.info("No extensions to start")
            return

        log.info("Running extension start phase...")
        await self._run_lifecycle_phase("initialize")

        log.info("Extension start complete")

    async def shutdown_extensions(self) -> None:
        """
        Run the close lifecycle phase for all extensions.
        """
        if not self._extensions:
            log.info("No extensions to shutdown")
            return

        log.info("Running extension shutdown phase...")
        await self._run_lifecycle_phase("close")

        log.info("Extension shutdown complete")

    async def _run_lifecycle_phase(self, phase: str) -> None:
        """
        Run a specific lifecycle phase on all extensions.

        Args:
            phase: The lifecycle phase to run ('discover', 'register', 'initialize', 'close')
        """
        errors = {}

        for name, extension in self._extensions.items():
            try:
                method = getattr(extension, phase)
                log.debug(f"Running {phase} on extension '{name}'")

                # Run the method (sync or async)
                if asyncio.iscoroutinefunction(method):
                    await method()
                else:
                    method()

            except Exception as e:
                log.error(f"Error in {phase} phase for extension '{name}': {e}")
                errors[name] = e

        # Store any errors for later reference
        if errors:
            self._extension_errors.update(errors)
            log.warning(f"{len(errors)} extensions had errors in {phase} phase")

    def get_extension(self, name: str) -> QiExtensionBase | None:
        """
        Get a loaded extension by name.

        Args:
            name: Extension name

        Returns:
            Extension instance or None if not found
        """
        return self._extensions.get(name)

    def list_extensions(self) -> list[str]:
        """
        Get list of loaded extension names.

        Returns:
            List of extension names
        """
        return list(self._extensions.keys())

    def get_failed_extensions(self) -> dict[str, Exception]:
        """
        Get extensions that failed to load.

        Returns:
            Dictionary mapping extension name to exception
        """
        return self._failed_extensions.copy()

    def get_extension_errors(self) -> dict[str, Exception]:
        """
        Get extensions that had lifecycle errors.

        Returns:
            Dictionary mapping extension name to exception
        """
        return self._extension_errors.copy()

    def get_stats(self) -> dict[str, int]:
        """
        Get extension manager statistics.

        Returns:
            Dictionary with loading statistics
        """
        return {
            "loaded": len(self._extensions),
            "failed": len(self._failed_extensions),
            "errors": len(self._extension_errors),
        }
