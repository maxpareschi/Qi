from typing import Any, Optional

from deepmerge import always_merger

from core.addon.manager import QiAddonManager
from core.db.manager import qi_db_manager
from core.logger import get_logger
from core.settings.base import QiGroup, QiSettings

log = get_logger(__name__)


class QiSettingsManager:
    """
    Orchestrates the collection, merging, and access of all settings.
    """

    def __init__(self, addon_manager: QiAddonManager):
        self._addon_manager = addon_manager
        self._db_manager = qi_db_manager
        self._root_settings = QiSettings(title="Qi Settings")
        self._is_built = False

    def _collect_addon_defaults(self) -> None:
        """
        Iterates through all loaded addons and collects their settings definitions.
        """
        log.info("Collecting settings definitions from all addons...")
        core_settings = QiGroup(title="Core")
        addon_settings = QiGroup(title="Addons")

        for addon in self._addon_manager.get_all_addons():
            try:
                addon_def = addon.get_settings_definition()
                if addon_def:
                    # Use __setattr__ directly since add_child is not implemented
                    setattr(addon_settings, addon.name, addon_def)
                    log.debug(f"Collected settings from addon: {addon.name}")
            except Exception:
                log.exception(f"Failed to get settings definition from {addon.name}")

        # Use __setattr__ directly since add_child is not implemented
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
        final_overrides = {}

        try:
            # 1. Load bundle-level overrides
            active_bundle = await self._db_manager.get_active_bundle()
            if active_bundle:
                bundle_overrides = await self._db_manager.get_settings("bundle")
                if bundle_overrides:
                    log.info(f"Applying '{active_bundle}' bundle overrides.")
                    always_merger.merge(final_overrides, bundle_overrides)

            # TODO: Load and merge project-level overrides
            # TODO: Load and merge user-level overrides

        except Exception:
            log.exception("Failed to load settings overrides from database.")

        return final_overrides

    async def build_settings(self) -> None:
        """
        Builds the final, effective settings model for the application.

        This is the main entry point for the manager. It orchestrates the
        collection of defaults, loading of overrides, and construction of the
        final Pydantic model.
        """
        if self._is_built:
            log.warning("Settings are already built. Ignoring request.")
            return

        log.info("--- Starting Settings Build ---")

        # 1. Collect all default settings from addons
        self._collect_addon_defaults()

        # 2. Load all overrides from the database
        overrides = await self._load_overrides()

        # 3. Apply overrides to the root settings object before building
        if overrides:
            self._root_settings.set_defaults(overrides)

        # 4. Build the final Pydantic model
        self._root_settings.build()
        self._is_built = True

        log.info("--- Finished Settings Build ---")
        if log.isEnabledFor(log.DEBUG):
            log.debug("Final effective settings:\n%s", self._root_settings.get_values())

    def get_value(self, path: str, default: Any = None) -> Any:
        """
        Retrieves a setting value by its dot-separated path.

        Example: `settings_manager.get_value("addons.my_addon.some_setting")`
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

        Args:
            path: Optional dot-separated path to get a specific part of the schema.
                 If not provided, returns the full schema.

        Returns:
            The JSON schema for the requested configuration section

        Raises:
            RuntimeError: If settings have not been built yet
            ValueError: If the requested path is not found in the schema
        """
        if not self._is_built:
            log.error("Cannot get schema: settings have not been built yet.")
            raise RuntimeError("Settings have not been built yet")

        schema = self._root_settings.get_model_schema()

        # If no path specified, return the full schema
        if not path:
            return schema

        # Navigate to the specified part of the schema
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

        Args:
            scope: The settings scope ('bundle', 'project', 'user')
            path: Dot-separated path to the setting
            value: New value for the setting

        Raises:
            RuntimeError: If settings have not been built yet
            ValueError: If scope is invalid or path is not valid
        """
        if not self._is_built:
            log.error("Cannot patch value: settings have not been built yet.")
            raise RuntimeError("Settings have not been built yet")

        if scope not in ("bundle", "project", "user"):
            raise ValueError(f"Invalid settings scope: {scope}")

        if not path:
            raise ValueError("Path cannot be empty")

        # 1. First determine if this is an addon setting or core setting
        parts = path.split(".")
        if len(parts) < 2:
            raise ValueError(
                f"Invalid settings path: {path}. Must have at least two parts."
            )

        top_level = parts[0]
        addon_name = None

        if top_level == "addons" and len(parts) >= 2:
            addon_name = parts[1]
            # Remove "addons.addon_name" prefix for storage
            setting_path = ".".join(parts[2:]) if len(parts) > 2 else ""
        elif top_level == "core":
            # Remove "core" prefix for storage
            setting_path = ".".join(parts[1:]) if len(parts) > 1 else ""
        else:
            raise ValueError(
                f"Invalid top-level setting: {top_level}. Must be 'core' or 'addons'."
            )

        # 2. Load current settings for this scope/addon
        current_settings = await self._db_manager.get_settings(scope, addon_name)
        if not current_settings:
            current_settings = {}

        # 3. Update the settings with the new value
        if setting_path:
            # Need to update a nested path
            target = current_settings
            path_parts = setting_path.split(".")

            # Navigate to the parent of the leaf node
            for i, part in enumerate(path_parts[:-1]):
                if part not in target:
                    target[part] = {}
                elif not isinstance(target[part], dict):
                    # If we encounter a non-dict value in the path, convert it to dict
                    target[part] = {}
                target = target[part]

            # Set the leaf value
            target[path_parts[-1]] = value
        else:
            # Direct setting at the root level
            current_settings = value

        # 4. Save the updated settings back to the database
        await self._db_manager.save_settings(scope, current_settings, addon_name)

        # 5. Update the in-memory settings model
        # We'll rebuild the entire settings model for simplicity
        # In a more optimized implementation, we could update just the specific path
        await self.build_settings()

        log.info(f"Updated setting {path} in {scope} scope")
