"""
File-based storage adapter for development and testing.

This adapter stores data in JSON files on the local filesystem.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from core.db.adapters import QiFileDbAdapter, StorageError
from core.logger import get_logger

log = get_logger(__name__)


class JsonFileDbAdapter(QiFileDbAdapter):
    """
    File-based storage adapter using JSON files.

    This adapter stores data in JSON files in a specified data directory.
    It organizes data by type (settings, bundles) and scope.
    """

    def __init__(self, data_dir: str):
        """
        Initialize the adapter with a data directory.

        Args:
            data_dir: Path to the directory where data files will be stored
        """
        self._data_dir = Path(data_dir).resolve()
        self._settings_dir = self._data_dir / "settings"
        self._bundles_dir = self._data_dir / "bundles"

        # Ensure directories exist
        self._settings_dir.mkdir(parents=True, exist_ok=True)
        self._bundles_dir.mkdir(parents=True, exist_ok=True)

        # Cache for loaded data with timestamps
        self._cache: dict[str, dict[str, Any]] = {}
        # Cache entry format: {key: {"data": data, "mtime": float, "load_time": float}}
        # "mtime" is the file's modification time (from time.time())
        # "load_time" is the monotonic time the cache entry was created (from time.monotonic())

        # Cache TTL in seconds
        self._cache_ttl = 10.0

        # Default bundle if none is set
        self._default_bundle = "production"

        # Ensure we have a bundles.json file with at least one bundle
        self._ensure_bundles_file()

        log.info(f"JsonFileDbAdapter initialized with data directory: {self._data_dir}")

    def _ensure_bundles_file(self) -> None:
        """Ensure the bundles.json file exists with default content."""
        bundles_file = self._bundles_dir / "bundles.json"

        if not bundles_file.exists():
            default_bundles = {
                "active": self._default_bundle,
                "bundles": {
                    "production": {
                        "name": "Production",
                        "description": "Default production bundle",
                        "addons": {},
                        "env": {},
                        "status": "production",
                    },
                    "staging": {
                        "name": "Staging",
                        "description": "Testing bundle for new features",
                        "addons": {},
                        "env": {},
                        "status": "staging",
                    },
                },
            }

            with open(bundles_file, "w") as f:
                json.dump(default_bundles, f, indent=2)

            log.info(f"Created default bundles file at {bundles_file}")

    def _is_cache_valid(self, key: str, file_path: Path) -> bool:
        """
        Check if the cached data for a key is still valid.

        A cache entry is valid if:
        1. It's within the TTL (time-to-live).
        2. The TTL has expired, but the underlying file has not been modified
           since the cache was last written.

        Args:
            key: The cache key.
            file_path: The path to the backing file.

        Returns:
            True if the cache is valid, False otherwise.
        """
        if key not in self._cache:
            return False

        cache_entry = self._cache[key]
        load_time = cache_entry.get("load_time", 0)

        # 1. Check if cache is fresh based on TTL (monotonic clock)
        if time.monotonic() - load_time < self._cache_ttl:
            return True

        # 2. TTL expired, check if the file on disk has been modified
        try:
            current_mtime = file_path.stat().st_mtime
            cached_mtime = cache_entry.get("mtime", 0)
            if current_mtime > cached_mtime:
                log.debug(f"Cache invalidated for '{key}': file modified on disk.")
                del self._cache[key]
                return False
        except (FileNotFoundError, PermissionError) as e:
            # If we can't stat the file, invalidate the cache to be safe
            log.warning(f"Could not stat file '{file_path}' for cache validation: {e}")
            del self._cache[key]
            return False

        # 3. TTL expired but file not modified. It's stale but not invalid.
        # We'll force a re-read by returning False. The get() method will
        # then overwrite the cache entry with fresh data and a new load_time.
        return False

    async def get(self, key: str) -> dict[str, Any] | None:
        """
        Retrieve data by key.

        Args:
            key: Path to the JSON file, relative to data_dir

        Returns:
            The loaded JSON data, or None if file not found
        """
        # Simulate I/O delay
        await asyncio.sleep(0.01)

        file_path = self._data_dir / key

        # Check if cache is valid
        if self._is_cache_valid(key, file_path):
            return self._cache[key]["data"]

        if not file_path.exists() or not file_path.is_file():
            # If file doesn't exist, ensure it's removed from cache
            if key in self._cache:
                del self._cache[key]
            return None

        try:
            mtime = file_path.stat().st_mtime
            with open(file_path, "r") as f:
                data = json.load(f)
                # Cache the data with current file mtime and monotonic load time
                self._cache[key] = {
                    "data": data,
                    "mtime": mtime,
                    "load_time": time.monotonic(),
                }
                return data
        except (json.JSONDecodeError, IOError, FileNotFoundError) as e:
            log.error(f"Error reading or decoding file {file_path}: {e}")
            # Ensure invalid entry is removed from cache
            if key in self._cache:
                del self._cache[key]
            return None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        """
        Store data by key.

        Args:
            key: Path to the JSON file, relative to data_dir
            value: Data to store (must be JSON serializable)
        """
        # Simulate I/O delay
        await asyncio.sleep(0.01)

        file_path = self._data_dir / key

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, "w") as f:
                json.dump(value, f, indent=2)

            # Update cache after successful write
            mtime = file_path.stat().st_mtime
            self._cache[key] = {
                "data": value,
                "mtime": mtime,
                "load_time": time.monotonic(),
            }
        except (TypeError, IOError) as e:
            log.error(f"Error writing to file {file_path}: {e}")
            raise StorageError(f"Failed to write data: {e}")

    async def delete(self, key: str) -> bool:
        """
        Delete data by key.

        Args:
            key: Path to the JSON file, relative to data_dir

        Returns:
            True if file was deleted, False if not found
        """
        # Simulate I/O delay
        await asyncio.sleep(0.01)

        file_path = self._data_dir / key

        if not file_path.exists():
            return False

        try:
            os.remove(file_path)

            # Remove from cache
            if key in self._cache:
                del self._cache[key]

            return True
        except IOError as e:
            log.error(f"Error deleting file {file_path}: {e}")
            return False

    def invalidate_cache(self, key: str = None) -> None:
        """
        Invalidate cache entries.

        Args:
            key: Specific key to invalidate, or None to invalidate all
        """
        if key is None:
            self._cache.clear()
            log.debug("Cleared entire cache")
        elif key in self._cache:
            del self._cache[key]
            log.debug(f"Invalidated cache for key: {key}")

    async def list_keys(self, prefix: str = "") -> list[str]:
        """
        list all keys (files) with an optional prefix.

        Args:
            prefix: Directory prefix to filter by

        Returns:
            list of keys (relative paths)
        """
        # Simulate I/O delay
        await asyncio.sleep(0.01)

        prefix_path = self._data_dir / prefix

        if not prefix_path.exists() or not prefix_path.is_dir():
            return []

        keys = []
        for root, _, files in os.walk(prefix_path):
            for file in files:
                if file.endswith(".json"):
                    rel_path = Path(root) / file
                    rel_key = rel_path.relative_to(self._data_dir).as_posix()
                    keys.append(rel_key)

        return keys

    async def get_settings(
        self, scope: str, addon: str | None = None
    ) -> dict[str, Any]:
        """
        Retrieve settings for a specific scope and optional addon.

        Args:
            scope: The settings scope ('bundle', 'project', 'user')
            addon: Optional addon name to filter by

        Returns:
            dictionary of settings
        """
        if scope not in ("bundle", "project", "user"):
            raise ValueError(f"Invalid settings scope: {scope}")

        # Construct the settings file path
        if addon:
            key = f"settings/{scope}/{addon}.json"
        else:
            key = f"settings/{scope}/core.json"

        settings = await self.get(key)
        return settings or {}

    async def save_settings(
        self, scope: str, settings: dict[str, Any], addon: str | None = None
    ) -> None:
        """
        Save settings for a specific scope and optional addon.

        Args:
            scope: The settings scope ('bundle', 'project', 'user')
            settings: dictionary of settings to save
            addon: Optional addon name to filter by
        """
        if scope not in ("bundle", "project", "user"):
            raise ValueError(f"Invalid settings scope: {scope}")

        # Construct the settings file path
        if addon:
            key = f"settings/{scope}/{addon}.json"
        else:
            key = f"settings/{scope}/core.json"

        await self.set(key, settings)
        log.info(f"Saved {scope} settings for {addon or 'core'}")

    async def list_bundles(self) -> list[dict[str, Any]]:
        """
        list all available bundles.

        Returns:
            list of bundle dictionaries
        """
        bundles_data = await self.get("bundles/bundles.json")

        if not bundles_data or "bundles" not in bundles_data:
            return []

        # Convert the bundles dict to a list of dicts with name included
        bundles_list = []
        for bundle_id, bundle_info in bundles_data["bundles"].items():
            bundle_dict = bundle_info.copy()
            bundle_dict["id"] = bundle_id
            bundles_list.append(bundle_dict)

        return bundles_list

    async def get_bundle(self, bundle_name: str) -> dict[str, Any] | None:
        """
        Get information about a specific bundle.

        Args:
            bundle_name: The name of the bundle

        Returns:
            Bundle information or None if not found
        """
        bundles_data = await self.get("bundles/bundles.json")

        if not bundles_data or "bundles" not in bundles_data:
            return None

        bundle_info = bundles_data["bundles"].get(bundle_name)
        if not bundle_info:
            return None

        # Include the bundle ID in the returned data
        bundle_dict = bundle_info.copy()
        bundle_dict["id"] = bundle_name

        return bundle_dict

    async def get_active_bundle(self) -> str:
        """
        Get the name of the currently active bundle.

        Returns:
            The name of the active bundle
        """
        bundles_data = await self.get("bundles/bundles.json")

        if not bundles_data or "active" not in bundles_data:
            return self._default_bundle

        return bundles_data["active"]

    async def set_active_bundle(self, bundle_name: str) -> None:
        """
        Set the active bundle.

        Args:
            bundle_name: The name of the bundle to activate

        Raises:
            ValueError: If bundle does not exist
        """
        bundles_data = await self.get("bundles/bundles.json")

        if not bundles_data or "bundles" not in bundles_data:
            raise ValueError("Bundles configuration not found")

        if bundle_name not in bundles_data["bundles"]:
            raise ValueError(f"Bundle '{bundle_name}' does not exist")

        # Update the active bundle
        bundles_data["active"] = bundle_name

        # Save the updated bundles configuration
        await self.set("bundles/bundles.json", bundles_data)

        log.info(f"Set active bundle to '{bundle_name}'")
