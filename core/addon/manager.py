from collections import defaultdict
from pathlib import Path

from core.addon.base import AddonRole, QiAddonBase
from core.addon.discovery import discover_addon_dirs, load_addon_from_path
from core.addon.exceptions import DuplicateRoleError, MissingProviderError
from core.logger import get_logger

log = get_logger(__name__)


class QiAddonManager:
    """
    Manages the discovery, loading, and lifecycle of all Qi addons.
    """

    def __init__(self, addon_paths: list[str]):
        self._addon_paths = addon_paths
        self._discovered_addons: dict[str, Path] = {}
        self._loaded_addons: dict[str, "QiAddonBase"] = {}
        self._providers: dict["AddonRole", "QiAddonBase"] = {}
        # A list of addons that have been loaded but not yet registered.
        self._pending_registration: list["QiAddonBase"] = []

    def discover_addons(self):
        """Scans the configured addon paths and populates the discovery registry."""
        log.info(f"Discovering addons from paths: {self._addon_paths}")
        self._discovered_addons = discover_addon_dirs(self._addon_paths)
        keys = self._discovered_addons.keys()
        log.info(f"Discovered {len(keys)} addons: {', '.join(keys)}")

    def load_provider_addons(self):
        """
        Phase 1 loading: Loads all addons, but only registers providers.

        This phase is critical for bootstrapping the application. It loads all
        addon code, identifies providers ('auth', 'db'), registers them, and
        queues all other addons for registration in Phase 2.
        """
        if not self._discovered_addons:
            self.discover_addons()

        log.info("--- Starting Addon Phase 1: Provider Loading ---")

        addons_by_role = defaultdict(list)

        for name, path in self._discovered_addons.items():
            addon = load_addon_from_path(name, path)
            self._loaded_addons[addon.name] = addon
            if addon.role in ("auth", "db"):
                addons_by_role[addon.role].append(addon)
            else:
                self._pending_registration.append(addon)

        # Validate and register core providers
        for role in ("auth", "db"):
            providers = addons_by_role.get(role, [])
            if not providers:
                raise MissingProviderError(role)
            if len(providers) > 1:
                raise DuplicateRoleError(role, [p.name for p in providers])

            provider = providers[0]
            self._providers[role] = provider
            log.info(f"Found '{role}' provider: '{provider.name}'")
            provider.discover()
            provider.register()
            log.info(f"Registered '{role}' provider: '{provider.name}'")

        log.info("--- Finished Addon Phase 1: Provider Loading ---")

    def load_regular_addons(self):
        """
        Phase 2 loading: Registers all non-provider addons and runs install hooks.

        This happens after authentication. It processes the addons queued
        during Phase 1.
        """
        log.info("--- Starting Addon Phase 2: Regular Addon Loading ---")

        for addon in self._pending_registration:
            log.debug(f"Registering regular addon: '{addon.name}'")
            addon.discover()
            addon.register()
            log.info(f"Registered regular addon: '{addon.name}'")

        self._pending_registration.clear()

        # The install hook runs on ALL addons after everyone is registered.
        log.info("Running install hooks on all addons...")
        for addon in self._loaded_addons.values():
            addon.install()

        log.info("--- Finished Addon Phase 2: Regular Addon Loading ---")

    def get_addon(self, name: str) -> "QiAddonBase | None":
        """Retrieves a loaded addon instance by name."""
        return self._loaded_addons.get(name)

    def get_all_addons(self) -> list["QiAddonBase"]:
        """Returns a list of all loaded addon instances."""
        return list(self._loaded_addons.values())

    def close_all(self):
        """Calls the 'close' method on all loaded addons for graceful shutdown."""
        log.info("Closing all addons...")
        for name, addon in self._loaded_addons.items():
            try:
                addon.close()
                log.info(f"Closed addon: '{name}'")
            except Exception:
                log.exception(f"Error closing addon '{name}'.")
