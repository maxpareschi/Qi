"""
Bundle Manager for Qi.

This module provides a manager for bundles, which are collections of addons
and environment variables that can be activated for a session.
"""

import asyncio
import os
import tomllib
from pathlib import Path
from typing import Dict, List, Optional

from core_new.abc import ManagerBase
from core_new.config import app_config
from core_new.di import container
from core_new.logger import get_logger
from core_new.models import QiBundle

log = get_logger("bundle.manager")


class BundleManager(ManagerBase):
    """
    Manager for addon bundles.

    This class manages the loading, activation, and environment setup for bundles.
    A bundle is a collection of addons and environment variables that can be
    activated for a session.
    """

    def __init__(self):
        """Initialize the bundle manager."""
        self._bundles: Dict[str, QiBundle] = {}
        self._active_bundle_name: str = ""

    async def initialize(self) -> None:
        """
        Initialize the bundle manager by loading bundles from the config file.
        """
        await self._load_bundles()

    async def start(self) -> None:
        """Starts the bundle manager. A no-op for this manager."""
        pass

    async def shutdown(self) -> None:
        """Shuts down the bundle manager. A no-op for this manager."""
        pass

    async def _load_bundles(self) -> None:
        """
        Load bundles from the TOML file specified in the config.
        """
        # Clear existing bundles for a clean load
        self._bundles.clear()

        bundles_file = Path(app_config.bundles_file)
        if not bundles_file.exists():
            log.warning(
                f"Bundles file not found at '{bundles_file}'. "
                f"Using default '{app_config.default_bundle_name}' bundle."
            )
            self._create_default_bundle()
            return

        try:
            with open(bundles_file, "rb") as f:
                bundles_data = tomllib.load(f)

            bundle_collection = bundles_data.get("bundles", {})

            for bundle_key, bundle_data in bundle_collection.items():
                if not isinstance(bundle_data, dict):
                    log.warning(
                        f"Invalid bundle data for key '{bundle_key}'. Skipping."
                    )
                    continue

                if "name" not in bundle_data or bundle_data["name"] != bundle_key:
                    log.warning(
                        f"Bundle name mismatch for key '{bundle_key}'. "
                        f"The bundle's 'name' property is '{bundle_data.get('name')}'. "
                        f"Bundle key must match bundle name. Skipping this bundle."
                    )
                    continue

                try:
                    # Create the bundle object
                    bundle = QiBundle(
                        name=bundle_data["name"],
                        allow_list=bundle_data.get("allow_list", []),
                        env=bundle_data.get("env", {}),
                    )
                    self._bundles[bundle_key] = bundle
                    log.debug(f"Loaded bundle: {bundle_key}")
                except Exception as e:
                    log.error(f"Error creating bundle '{bundle_key}': {e}")

            if not self._bundles:
                # If no valid bundles were found, create a default one
                log.warning("No valid bundles found. Creating default bundle.")
                self._create_default_bundle()

            log.info(f"Loaded {len(self._bundles)} bundles from '{bundles_file}'.")

            # Set the initial active bundle
            self._set_initial_active_bundle()

        except Exception as e:
            log.error(f"Failed to load bundles file '{bundles_file}': {e}")
            self._create_default_bundle()

    def _create_default_bundle(self) -> None:
        """Create a default bundle when no bundles are available."""
        self._bundles.clear()
        default_name = app_config.default_bundle_name
        default_bundle = QiBundle(name=default_name, allow_list=[], env={})
        self._bundles[default_name] = default_bundle
        self._active_bundle_name = default_name
        log.info(f"Created default bundle: '{default_name}'")

    def _set_initial_active_bundle(self) -> None:
        """Set the initial active bundle based on the fallback order."""
        for bundle_name in app_config.bundle_fallback_order:
            if bundle_name in self._bundles:
                self._active_bundle_name = bundle_name
                log.info(
                    f"Active bundle set to '{bundle_name}' based on fallback priority."
                )
                return

        # If no fallback bundle is found, use the first one available
        if self._bundles:
            self._active_bundle_name = next(iter(self._bundles))
            log.info(
                f"No preferred bundle found. "
                f"Active bundle set to first available: '{self._active_bundle_name}'."
            )
        else:
            # This should not happen as we create a default bundle if none are loaded
            log.error(
                "No bundles available. Bundle system is in an inconsistent state."
            )
            raise RuntimeError("No bundles available after loading process.")

    def list_bundles(self) -> List[str]:
        """
        Get a list of available bundle names.

        Returns:
            A list of bundle names
        """
        return list(self._bundles.keys())

    def get_bundle(self, bundle_name: str) -> Optional[QiBundle]:
        """
        Get a bundle by name.

        Args:
            bundle_name: The name of the bundle to retrieve

        Returns:
            The bundle if found, otherwise None
        """
        return self._bundles.get(bundle_name)

    def get_active_bundle(self) -> QiBundle:
        """
        Get the currently active bundle.

        Returns:
            The active bundle

        Raises:
            RuntimeError: If no active bundle is set
        """
        if (
            not self._active_bundle_name
            or self._active_bundle_name not in self._bundles
        ):
            raise RuntimeError("No active bundle is set")
        return self._bundles[self._active_bundle_name]

    async def set_active_bundle(self, bundle_name: str) -> bool:
        """
        Set the active bundle by name.

        Args:
            bundle_name: The name of the bundle to set as active

        Returns:
            True if the bundle was successfully set, False otherwise
        """
        if bundle_name not in self._bundles:
            log.warning(
                f"Attempted to set non-existent bundle '{bundle_name}' as active."
            )
            return False

        if bundle_name == self._active_bundle_name:
            return True  # No change needed

        self._active_bundle_name = bundle_name
        log.info(f"Active bundle changed to '{bundle_name}'.")

        # Notify other systems that the active bundle has changed
        hub = container.get("hub")
        asyncio.create_task(hub.fire_event("bundle.active.changed"))

        return True

    def apply_bundle_env(self) -> None:
        """
        Apply the environment variables from the active bundle to the current process.
        """
        try:
            active_bundle = self.get_active_bundle()
            bundle_env = active_bundle.env

            if not bundle_env:
                log.info("No environment variables to apply for the active bundle.")
                return

            log.info(
                f"Applying environment variables for bundle '{active_bundle.name}'"
            )
            os.environ.update(bundle_env)

        except Exception as e:
            log.error(f"Error applying bundle environment variables: {e}")


# Register the bundle manager as a singleton service
container.register_singleton("bundle_manager", lambda: BundleManager())
