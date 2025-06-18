from typing import Any, Optional

from deepmerge import always_merger

from core.addon.manager import QiAddonManager
from core.bundle.manager import qi_bundle_manager
from core.db.manager import qi_db_manager
from core.logger import get_logger
from core.settings.base import QiGroup, QiSettings

log = get_logger(__name__)


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


class QiSettingsManager:
    """
    Orchestrates the collection, merging, and access of all settings.
    """

    def __init__(self, addon_manager: QiAddonManager):
        self._addon_manager = addon_manager
        self._bundle_manager = qi_bundle_manager
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
            # 1. Load bundle-level overrides for the active bundle
            active_bundle_name = self._bundle_manager.get_active_bundle().name
            all_bundle_overrides = await self._db_manager.get_settings("bundle")

            if active_bundle_name in all_bundle_overrides:
                bundle_overrides = all_bundle_overrides[active_bundle_name]
                log.info(f"Applying '{active_bundle_name}' bundle overrides.")
                always_merger.merge(final_overrides, bundle_overrides)

            # TODO: Load and merge project-level overrides
            # active_project_name = "some_project"
            # all_project_overrides = await self._db_manager.get_settings("project")
            # if active_project_name in all_project_overrides:
            #     always_merger.merge(final_overrides, all_project_overrides[active_project_name])

            # TODO: Load and merge user-level overrides
            # current_user_id = "some_user"
            # all_user_overrides = await self._db_manager.get_settings("user")
            # if current_user_id in all_user_overrides:
            #     always_merger.merge(final_overrides, all_user_overrides[current_user_id])

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

        if not path or not isinstance(path, str):
            raise ValueError("Path must be a non-empty string")

        # For now, all patches are applied to the active bundle's settings.
        # This could be extended to allow patching project/user scopes.
        if scope != "bundle":
            raise NotImplementedError(
                "Currently, only 'bundle' scope patching is supported."
            )

        # 1. Get the name of the bundle to be patched.
        active_bundle_name = self._bundle_manager.get_active_bundle().name

        # 2. Load all current settings for the 'bundle' scope.
        all_bundle_settings = await self._db_manager.get_settings("bundle")
        if not isinstance(all_bundle_settings, dict):
            all_bundle_settings = {}

        # 3. Get or create the settings dict for the specific active bundle.
        target_bundle_settings = all_bundle_settings.setdefault(active_bundle_name, {})

        # 4. Update the settings dict with the new value at the specified path.
        _set_nested_value(target_bundle_settings, path, value)

        # 5. Save the entire updated settings object back to the database.
        await self._db_manager.save_settings(scope, all_bundle_settings)

        # 6. Rebuild the in-memory settings model to apply the change.
        # This is inefficient for frequent updates but guarantees consistency.
        log.debug(f"Rebuilding settings model to apply patch for '{path}'...")
        self._is_built = False  # Allow build_settings to run again
        await self.build_settings()

        log.info(
            f"Updated setting '{path}' in '{scope}' scope for bundle '{active_bundle_name}'."
        )
