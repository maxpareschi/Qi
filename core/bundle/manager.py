# core/bundle/manager.py

"""
This module contains the manager for all Qi bundles.
"""

from __future__ import annotations

import asyncio
import tomllib
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from core.config import qi_launch_config
from core.logger import get_logger
from core.messaging.hub import qi_hub
from core.models import QiBundle, QiBundleCollection

log = get_logger(__name__)


class QiBundleManager:
    """
    Manages addon bundles for Qi.

    - Loads bundle definitions from a TOML file.
    - Manages the active bundle.
    - Provides environment variables for the active bundle.
    """

    def __init__(self):
        self._bundles: dict[str, QiBundle] = {}
        self._active_bundle_name: str = ""
        self._load_bundles()

    def _load_bundles(self) -> None:
        """Loads bundles from the TOML file specified in the launch config."""
        # Clear existing bundles for a clean load
        self._bundles.clear()

        bundles_file = Path(qi_launch_config.bundles_file)
        if not bundles_file.exists():
            log.warning(
                f"Bundles file not found at '{bundles_file}'. "
                f"Using default '{qi_launch_config.default_bundle_name}' bundle."
            )
            self._create_default_bundle()
            return

        try:
            with open(bundles_file, "rb") as f:
                bundles_data = tomllib.load(f)
            parsed_bundles = QiBundleCollection.model_validate(bundles_data)

            for bundle_key, bundle_data in parsed_bundles.bundles.items():
                if bundle_key != bundle_data.name:
                    log.error(
                        f"Bundle name mismatch for key '{bundle_key}'. "
                        f"The bundle's 'name' property is '{bundle_data.name}'. "
                        f"Bundle key must match bundle name. Skipping this bundle."
                    )
                    continue
                try:
                    # Validate each bundle individually
                    self._bundles[bundle_key] = QiBundle.model_validate(bundle_data)
                except ValidationError as e:
                    log.error(
                        f"Skipping invalid bundle '{bundle_key}' in '{bundles_file}': {e}"
                    )

            if not self._bundles:
                # If the file exists and was parsed but no valid bundles were found,
                # raise an error instead of falling back to the default
                error_msg = "No bundles available after loading process."
                log.error(f"{error_msg}")
                raise RuntimeError(error_msg)

            log.info(f"Loaded {len(self._bundles)} bundles from '{bundles_file}'.")

        except (
            tomllib.TOMLDecodeError,
            ValueError,
            ValidationError,
            IOError,
            PermissionError,
        ) as e:
            log.error(
                f"Failed to load or parse bundles file '{bundles_file}': {e}. "
                f"Using default '{qi_launch_config.default_bundle_name}' bundle."
            )
            self._create_default_bundle()

        # Determine and set the active bundle using the fallback order
        self._set_initial_active_bundle()

    def _set_initial_active_bundle(self):
        """Sets the initial active bundle based on the fallback order."""
        for bundle_name in qi_launch_config.bundle_fallback_order:
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

    def _create_default_bundle(self):
        """Creates and sets a single default bundle."""
        self._bundles.clear()
        default_name = qi_launch_config.default_bundle_name
        default_bundle = QiBundle(name=default_name, allow_list=[], env={})
        self._bundles[default_name] = default_bundle
        self._active_bundle_name = default_name

    def list_bundles(self) -> list[str]:
        """Returns a list of available bundle names."""
        return list(self._bundles.keys())

    def get_bundle(self, bundle_name: str) -> QiBundle | None:
        """
        Retrieves a bundle by its name.

        Args:
            bundle_name: The name of the bundle to retrieve.

        Returns:
            The Bundle object if found, otherwise None.
        """
        return self._bundles.get(bundle_name)

    def get_active_bundle(self) -> QiBundle:
        """Returns the currently active bundle object."""
        return self._bundles[self._active_bundle_name]

    def set_active_bundle(self, bundle_name: str) -> bool:
        """
        Sets the active bundle by name.

        Args:
            bundle_name: The name of the bundle to set as active.

        Returns:
            True if the bundle was successfully set, False otherwise.
        """
        if bundle_name not in self._bundles:
            log.warning(
                f"Attempted to set non-existent bundle '{bundle_name}' as active."
            )
            return False

        if bundle_name == self._active_bundle_name:
            return True  # No change, no need to fire event

        self._active_bundle_name = bundle_name
        log.info(f"Active bundle changed to '{bundle_name}'.")

        # Notify other systems that the active bundle has changed.
        # This is crucial for services like the settings manager to reload.
        asyncio.create_task(qi_hub.fire_event("bundle.active.changed"))

        return True

    def env_for_bundle(self, name: str | None = None) -> dict[str, str]:
        """
        Returns the environment variables for a given bundle name.
        If no name is provided, returns the environment for the active bundle.
        """
        bundle_name = name or self._active_bundle_name
        bundle = self.get_bundle(bundle_name)
        return bundle.env if bundle else {}


# Singleton instance of the bundle manager
qi_bundle_manager: Final[QiBundleManager] = QiBundleManager()
