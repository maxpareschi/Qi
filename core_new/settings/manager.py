# core_new/settings/manager.py

"""
This module contains the manager for the Qi settings.
"""

import asyncio
from typing import Any, Optional

from deepmerge import always_merger

from core_new.abc import ManagerBase
from core_new.addon.manager import AddonManager
from core_new.bundle.manager import BundleManager
from core_new.db.manager import DatabaseManager
from core_new.di import container
from core_new.logger import get_logger
from core_new.messaging.hub import Hub
from core_new.settings.base import QiGroup, QiSettings

log = get_logger("settings.manager")


def _set_nested_value(data: dict, path: str, value: Any) -> None:
    """Sets a value in a nested dictionary using a dot-separated path."""
    if not path or not isinstance(path, str):
        raise ValueError("Path must be a non-empty string")

    keys = path.split(".")
    current_level = data
    for i, key in enumerate(keys[:-1]):
        current_level = current_level.setdefault(key, {})
        if not isinstance(current_level, dict):
            log.warning(
                f"Cannot set nested value for path '{path}'. Part '{key}' is not a dictionary."
            )
            # Overwrite the non-dict part to proceed
            current_level = {}
            if i > 0:
                parent_level = data
                for p_key in keys[:i]:
                    parent_level = parent_level[p_key]
                parent_level[key] = current_level
    current_level[keys[-1]] = value


def _flatten_dict(
    d: dict, parent_key: str = "", sep: str = "."
) -> list[tuple[str, Any]]:
    """
    Flatten a nested dictionary into a list of (path, value) tuples.

    Args:
        d: The dictionary to flatten
        parent_key: The parent key for recursion
        sep: The separator to use in paths

    Returns:
        A list of (path, value) tuples where path is a dot-separated string
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict) and v:
            items.extend(_flatten_dict(v, new_key, sep=sep))
        else:
            items.append((new_key, v))
    return items


class SettingsManager(ManagerBase):
    """
    Orchestrates the collection, merging, and access of all settings.
    """

    def __init__(self):
        """Initialize the settings manager."""
        self._root_settings = QiSettings(title="Qi Settings")
        self._is_built = False
        self._build_lock = asyncio.Lock()

    def _register_bundle_change_handler(self):
        """Register a handler for bundle changes to trigger a settings rebuild."""
        hub: Hub = container.get("hub")
        hub.on_event("bundle.active.changed")(self.rebuild)
        log.info("Registered settings manager to listen for bundle changes.")

    def _collect_addon_defaults(self) -> None:
        """
        Iterates through all loaded addons and collects their settings definitions.
        """
        log.info("Collecting settings definitions from all addons...")
        addon_manager = container.get_typed("addon_manager", AddonManager)

        core_settings = QiGroup(title="Core")
        addon_settings = QiGroup(title="Addons")

        for addon in addon_manager.get_all_addons():
            try:
                addon_def = addon.get_settings_definition()
                if addon_def:
                    setattr(addon_settings, addon.name, addon_def)
                    log.debug(f"Collected settings from addon: {addon.name}")
            except (AttributeError, TypeError, ValueError) as e:
                log.warning(f"Failed to get settings definition from {addon.name}: {e}")
            except Exception as e:
                log.error(
                    f"Unexpected error getting settings from {addon.name}: {e}",
                    exc_info=True,
                )

        setattr(self._root_settings, "core", core_settings)
        setattr(self._root_settings, "addons", addon_settings)
        log.info("Finished collecting addon settings definitions.")

    async def _load_overrides(self) -> dict[str, Any]:
        """
        Loads all settings overrides from the database for the current context.

        The merge order is:
        1. Bundle Overrides
        2. Project Overrides (TODO)
        3. User Overrides (TODO)
        """
        log.info("Loading settings overrides...")
        bundle_manager = container.get_typed("bundle_manager", BundleManager)
        db_manager = container.get_typed("db_manager", DatabaseManager)
        final_overrides = {}

        try:
            # 1. Load bundle-level overrides for the active bundle
            active_bundle_name = bundle_manager.get_active_bundle().name
            all_bundle_overrides = await db_manager.get_settings("bundle")
            bundle_overrides = all_bundle_overrides.get(active_bundle_name, {})

            if bundle_overrides:
                log.info(f"Applying '{active_bundle_name}' bundle overrides.")
                always_merger.merge(final_overrides, bundle_overrides)

        except (ConnectionError, TimeoutError) as e:
            log.warning(
                f"Database connection issue while loading settings overrides: {e}"
            )
        except (KeyError, ValueError) as e:
            log.warning(f"Data format issue while loading settings overrides: {e}")
        except Exception as e:
            log.error(
                f"Unexpected error loading settings overrides: {e}", exc_info=True
            )

        return final_overrides

    async def initialize(self) -> None:
        """Initialize the settings manager."""
        # Register for bundle change events
        self._register_bundle_change_handler()

        # Perform initial build
        await self._build_settings()

    async def _build_settings(self) -> None:
        """
        Build the settings model by collecting addon definitions and applying overrides.
        """
        async with self._build_lock:
            log.info("Building settings model...")
            self._is_built = False

            # Collect settings definitions from addons
            self._collect_addon_defaults()

            # Load overrides from database
            overrides = await self._load_overrides()

            # Apply overrides to the model
            if overrides:
                log.info("Applying settings overrides...")
                # Build the model first to ensure proper structure
                self._root_settings.build()

                # Apply overrides to the built model
                for path, value in _flatten_dict(overrides):
                    try:
                        # Use dot notation to set nested values in the model
                        _set_nested_value(self._root_settings.get_values(), path, value)
                        log.debug(f"Applied override for setting: {path}")
                    except Exception as e:
                        log.warning(f"Failed to apply override for {path}: {e}")
            else:
                # Just build the model without overrides
                self._root_settings.build()

            # Mark as built
            self._is_built = True
            log.info("Settings model built successfully.")

    async def start(self) -> None:
        """Settings manager has no start-up actions after initialization."""
        pass

    async def shutdown(self) -> None:
        """A no-op for this manager."""
        pass

    async def rebuild(self) -> None:
        """
        Forces a rebuild of the settings. This is triggered by system
        events like the active bundle changing. The lock ensures that this
        doesn't conflict with other operations like patching.
        """
        log.info("Rebuilding settings due to system event (e.g., bundle change).")
        self._root_settings = QiSettings(title="Qi Settings")  # Reset
        await self._build_settings()

    def get_value(self, path: str, default: Any = None) -> Any:
        """
        Retrieves a setting value by its dot-separated path.
        """
        if not self._is_built:
            log.error("Cannot get value: settings have not been built yet.")
            return default

        keys = path.split(".")
        value = self._root_settings.get_values()
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            log.warning(f"Settings path not found: {path}")
            return default

    def get_schema(self, path: Optional[str] = None) -> dict[str, Any]:
        """
        Retrieves the JSON schema for settings.
        """
        if not self._is_built:
            log.error("Cannot get schema: settings have not been built yet.")
            raise RuntimeError("Settings have not been built yet")

        schema = self._root_settings.get_model_schema()

        if not path:
            return schema

        parts = path.split(".")
        current = schema

        for part in parts:
            if "properties" in current and part in current["properties"]:
                current = current["properties"][part]
            else:
                raise ValueError(f"Path {path} not found in schema")

        return current

    async def patch_value(self, scope: str, path: str, value: Any) -> None:
        """
        Updates a setting value and persists it to the database.
        """
        if not self._is_built:
            log.error("Cannot patch value: settings have not been built yet.")
            raise RuntimeError("Settings have not been built yet")

        bundle_manager = container.get_typed("bundle_manager", BundleManager)
        db_manager = container.get_typed("db_manager", DatabaseManager)

        async with self._build_lock:
            if scope not in ("bundle", "project", "user"):
                raise ValueError(f"Invalid settings scope: {scope}")

            if not path or not isinstance(path, str):
                raise ValueError("Path must be a non-empty string")

            if scope != "bundle":
                raise NotImplementedError(
                    "Currently, only 'bundle' scope patching is supported."
                )

            active_bundle_name = bundle_manager.get_active_bundle().name
            all_bundle_settings = await db_manager.get_settings("bundle")

            target_bundle_settings = all_bundle_settings.setdefault(
                active_bundle_name, {}
            )

            _set_nested_value(target_bundle_settings, path, value)

            await db_manager.save_settings("bundle", all_bundle_settings)

            await self.rebuild()

            log.info(
                f"Updated setting '{path}' in '{scope}' scope for bundle '{active_bundle_name}'."
            )


# Register the settings manager as a singleton service
container.register_singleton("settings_manager", lambda: SettingsManager())
