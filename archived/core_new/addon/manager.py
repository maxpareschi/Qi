"""
Addon Manager for Qi.

This module provides a manager for discovering, loading, and managing addons.
"""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from core_new.abc import ManagerBase
from core_new.addon.base import (
    AddonRole,
    DuplicateRoleError,
    MissingProviderError,
    QiAddonBase,
)
from core_new.addon.discovery import discover_addon_dirs, load_addon_from_path
from core_new.addon.json_db_addon import NewJsonFileDbAddon
from core_new.addon.mock_auth_addon import NewMockAuthAddon
from core_new.logger import get_logger

log = get_logger("addon.manager")


class AddonManager(ManagerBase):
    """
    Manager for Qi addons.

    This class manages the discovery, loading, and lifecycle of all addons.
    It provides a two-phase loading process to ensure that provider addons
    (auth, db) are loaded before other addons.
    """

    def __init__(self):
        """Initialize the addon manager."""
        self._addon_paths: List[str] = []
        self._discovered_addons: Dict[str, Path] = {}
        self._loaded_addons: Dict[str, QiAddonBase] = {}
        self._providers: Dict[AddonRole, QiAddonBase] = {}
        # A list of addons that have been loaded but not yet registered.
        self._pending_registration: List[QiAddonBase] = []
        # Track failed addons to avoid retrying them
        self._failed_addons: Dict[str, Exception] = {}
        # Track addons with non-fatal registration errors
        self._addons_with_errors: Dict[str, Exception] = {}

    async def initialize(self) -> None:
        """Initializes the addon manager. A no-op as discovery is orchestrated by the Application."""
        pass

    async def start(self) -> None:
        """Starts the addon manager. A no-op for this manager."""
        pass

    def discover_addons(self, addon_paths: List[str]) -> None:
        """
        Scans the configured addon paths and populates the discovery registry.

        Args:
            addon_paths: A list of paths to directories containing addons
        """
        self._addon_paths = addon_paths
        log.info(f"Discovering addons from paths: {self._addon_paths}")
        self._discovered_addons = discover_addon_dirs(self._addon_paths)
        keys = list(self._discovered_addons.keys())
        log.info(f"Discovered {len(keys)} external addons: {', '.join(keys)}")

    def load_provider_addons(self) -> None:
        """
        Phase 1 loading: Loads all addons, but only registers providers.

        This phase is critical for bootstrapping the application. It loads all
        addon code, identifies providers ('auth', 'db'), registers them, and
        queues all other addons for registration in Phase 2.
        """
        if not self._discovered_addons:
            self.discover_addons()

        log.info("--- Starting Addon Phase 1: Provider Loading ---")

        # 1. Instantiate default internal providers

        default_addons: Dict[str, QiAddonBase] = {
            "core_mock_auth": NewMockAuthAddon(),
            "core_json_db": NewJsonFileDbAddon(),
        }

        # 2. Load discovered external addons
        discovered_addons: Dict[str, QiAddonBase] = {}
        for name, path in self._discovered_addons.items():
            try:
                addon = load_addon_from_path(name, path)
                discovered_addons[name] = addon
            except Exception as e:
                log.error(f"Failed to load addon '{name}': {e}")
                self._failed_addons[name] = e

        # 3. Merge addons, allowing external addons to override defaults
        # First, add all discovered addons
        final_addons = discovered_addons.copy()

        # Then add default addons only if no addon with that name was discovered
        for name, addon in default_addons.items():
            if name not in final_addons:
                final_addons[name] = addon
                log.info(f"Using default internal provider: {name}")

        # 4. Categorize addons by role
        addons_by_role: Dict[str, List[QiAddonBase]] = defaultdict(list)
        for name, addon in final_addons.items():
            self._loaded_addons[name] = addon
            if addon.role in ("auth", "db"):
                addons_by_role[addon.role].append(addon)
            else:
                self._pending_registration.append(addon)

        # 5. Validate and register core providers
        for role in ("auth", "db"):
            providers = addons_by_role.get(role, [])
            if not providers:
                raise MissingProviderError(role)
            if len(providers) > 1:
                raise DuplicateRoleError(role, [p.name for p in providers])

            provider = providers[0]
            self._providers[role] = provider
            log.info(f"Found '{role}' provider: '{provider.name}'")

            try:
                provider.discover()
                provider.register()
                log.info(f"Registered '{role}' provider: '{provider.name}'")
            except Exception as e:
                # Provider registration failure is fatal
                log.critical(
                    f"Failed to register critical '{role}' provider '{provider.name}': {e}"
                )
                raise

        log.info("--- Finished Addon Phase 1: Provider Loading ---")

        if self._failed_addons:
            log.warning(
                f"Failed to load {len(self._failed_addons)} addons during Phase 1"
            )

    def load_regular_addons(self) -> None:
        """
        Phase 2 loading: Registers all non-provider addons and runs install hooks.

        This happens after authentication. It processes the addons queued
        during Phase 1.
        """
        log.info("--- Starting Addon Phase 2: Regular Addon Loading ---")

        successful_addons = []

        for addon in self._pending_registration:
            try:
                log.debug(f"Registering regular addon: '{addon.name}'")
                addon.discover()
                addon.register()
                log.info(f"Registered regular addon: '{addon.name}'")
                successful_addons.append(addon)
            except Exception as e:
                log.error(f"Failed to register addon '{addon.name}': {e}")
                self._addons_with_errors[addon.name] = e
                # Continue with other addons

        self._pending_registration.clear()

        # The install hook runs on ALL addons after everyone is registered.
        log.info("Running install hooks on all addons...")

        # First run install on providers
        for role, provider in self._providers.items():
            try:
                provider.install()
                log.debug(f"Ran install hook for '{role}' provider: '{provider.name}'")
            except Exception as e:
                log.error(
                    f"Error in install hook for '{role}' provider '{provider.name}': {e}"
                )
                self._addons_with_errors[provider.name] = e

        # Then run install on regular addons
        for addon in successful_addons:
            try:
                addon.install()
                log.debug(f"Ran install hook for addon: '{addon.name}'")
            except Exception as e:
                log.error(f"Error in install hook for addon '{addon.name}': {e}")
                self._addons_with_errors[addon.name] = e

        log.info("--- Finished Addon Phase 2: Regular Addon Loading ---")

        if self._addons_with_errors:
            log.warning(
                f"{len(self._addons_with_errors)} addons had errors during registration or installation"
            )

    def get_addon(self, name: str) -> Optional[QiAddonBase]:
        """
        Retrieves a loaded addon instance by name.

        Args:
            name: The name of the addon to retrieve

        Returns:
            The addon instance if found, otherwise None
        """
        return self._loaded_addons.get(name)

    def get_all_addons(self) -> List[QiAddonBase]:
        """
        Returns a list of all loaded addon instances.

        Returns:
            A list of all loaded addon instances
        """
        return list(self._loaded_addons.values())

    def get_failed_addons(self) -> Dict[str, Exception]:
        """
        Returns a dictionary of addons that failed to load with their exceptions.

        Returns:
            A dictionary mapping addon names to exceptions
        """
        return self._failed_addons.copy()

    def get_addons_with_errors(self) -> Dict[str, Exception]:
        """
        Returns a dictionary of addons that had non-fatal errors during registration or installation.

        Returns:
            A dictionary mapping addon names to exceptions
        """
        return self._addons_with_errors.copy()

    def is_provider_available(self, role: AddonRole) -> bool:
        """
        Checks if a provider with the specified role is available.

        Args:
            role: The role to check for

        Returns:
            True if a provider with the specified role is available, otherwise False
        """
        return role in self._providers

    def get_provider(self, role: AddonRole) -> Optional[QiAddonBase]:
        """
        Gets the provider addon for a specific role.

        Args:
            role: The role to get the provider for

        Returns:
            The provider addon if found, otherwise None
        """
        return self._providers.get(role)

    async def shutdown(self) -> None:
        """
        Calls the 'close' method on all loaded addons for graceful shutdown.
        """
        log.info("Closing all addons...")
        close_errors = {}

        # Close providers last
        regular_addons = {
            name: addon
            for name, addon in self._loaded_addons.items()
            if addon.role not in ("auth", "db")
        }

        # First close regular addons
        for name, addon in regular_addons.items():
            try:
                addon.close()
                log.info(f"Closed addon: '{name}'")
            except Exception as e:
                log.exception(f"Error closing addon '{name}'")
                close_errors[name] = e

        # Then close providers in reverse order of importance
        for role in ("db", "auth"):  # Reverse order - close auth last
            provider = self._providers.get(role)
            if provider:
                try:
                    provider.close()
                    log.info(f"Closed '{role}' provider: '{provider.name}'")
                except Exception as e:
                    log.exception(f"Error closing '{role}' provider '{provider.name}'")
                    close_errors[provider.name] = e

        if close_errors:
            log.warning(f"Encountered {len(close_errors)} errors while closing addons")
