# core/db/file_db.py

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
    It organizes data by type (settings, etc.) and scope.
    It is designed to be async-safe and performant by offloading file I/O
    to a thread pool and using per-file locks to prevent race conditions.
    """

    def __init__(self, data_dir: str):
        """
        Initialize the adapter with a data directory.

        Args:
            data_dir: Path to the directory where data files will be stored
        """
        self._data_dir = Path(data_dir).resolve()
        self._settings_dir = self._data_dir / "settings"

        # Ensure directories exist
        self._settings_dir.mkdir(parents=True, exist_ok=True)

        # Cache for loaded data with timestamps
        self._cache: dict[str, dict[str, Any]] = {}
        # Cache entry format: {key: {"data": data, "mtime": float, "load_time": float}}
        # "mtime" is the file's modification time (from os.path.getmtime)
        # "load_time" is the monotonic time the cache entry was created (from time.monotonic())
        self._cache_ttl = 5.0  # seconds

        # Per-file locks to prevent race conditions on file read/writes
        self._file_locks: dict[Path, asyncio.Lock] = {}
        self._master_lock = asyncio.Lock()  # To protect access to _file_locks

        log.info(f"JsonFileDbAdapter initialized with data directory: {self._data_dir}")

    async def _get_lock(self, file_path: Path) -> asyncio.Lock:
        """Get or create a lock for a specific file path."""
        async with self._master_lock:
            if file_path not in self._file_locks:
                self._file_locks[file_path] = asyncio.Lock()
            return self._file_locks[file_path]

    def _get_path_for_scope(self, scope: str) -> Path:
        """Constructs the file path for a given settings scope."""
        if scope not in ("bundle", "project", "user"):
            raise ValueError(f"Invalid settings scope: {scope}")
        return self._settings_dir / f"{scope}.json"

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

        # 3. TTL expired but file not modified.
        # We'll re-read to be safe, but this could be optimized if needed.
        return False

    async def get(self, key: str) -> dict[str, Any] | None:
        """
        Retrieve data by key (file path relative to data_dir).

        Args:
            key: Path to the JSON file, relative to data_dir

        Returns:
            The loaded JSON data, or None if file not found
        """
        file_path = self._data_dir / key
        lock = await self._get_lock(file_path)

        async with lock:
            # Check if cache is valid
            if self._is_cache_valid(key, file_path):
                log.debug(f"Cache hit for '{key}'")
                return self._cache[key].get("data")

            exists = await asyncio.to_thread(file_path.is_file)
            if not exists:
                if key in self._cache:
                    del self._cache[key]
                return None

            try:
                mtime = (await asyncio.to_thread(file_path.stat)).st_mtime

                def _read_file():
                    with open(file_path, "r", encoding="utf-8") as f:
                        return json.load(f)

                data = await asyncio.to_thread(_read_file)

                self._cache[key] = {
                    "data": data,
                    "mtime": mtime,
                    "load_time": time.monotonic(),
                }
                log.debug(f"Cache miss for '{key}', loaded from disk.")
                return data
            except (json.JSONDecodeError, IOError, FileNotFoundError) as e:
                log.error(f"Error reading or decoding file {file_path}: {e}")
                if key in self._cache:
                    del self._cache[key]
                raise StorageError(f"Failed to read data: {e}")

    async def set(self, key: str, value: dict[str, Any]) -> None:
        """
        Store data by key (file path relative to data_dir).

        Args:
            key: Path to the JSON file, relative to data_dir
            value: Data to store (must be JSON serializable)
        """
        file_path = self._data_dir / key
        lock = await self._get_lock(file_path)

        async with lock:
            await asyncio.to_thread(file_path.parent.mkdir, parents=True, exist_ok=True)

            try:
                temp_file_path = file_path.with_suffix(f"{file_path.suffix}.tmp")

                def _write_file():
                    with open(temp_file_path, "w", encoding="utf-8") as f:
                        json.dump(value, f, indent=2)
                    os.replace(temp_file_path, file_path)

                await asyncio.to_thread(_write_file)

                mtime = (await asyncio.to_thread(file_path.stat)).st_mtime
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
        Delete data by key (file path relative to data_dir).

        Args:
            key: Path to the JSON file, relative to data_dir

        Returns:
            True if file was deleted, False if not found
        """
        file_path = self._data_dir / key
        lock = await self._get_lock(file_path)

        async with lock:
            exists = await asyncio.to_thread(file_path.exists)
            if not exists:
                return False

            try:
                await asyncio.to_thread(os.remove, file_path)
                log.info(f"Deleted file: {file_path}")

                if key in self._cache:
                    del self._cache[key]

                return True
            except IOError as e:
                log.error(f"Error deleting file {file_path}: {e}")
                raise StorageError(f"Failed to delete data: {e}")

    def invalidate_cache(self, key: str | None = None) -> None:
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
        List all keys (file paths) in the data directory.
        An empty prefix lists all keys.
        """

        # This method doesn't modify files, so locking is less critical,
        # but wrapping in to_thread is good practice for potentially slow I/O.
        def _list_files():
            start_path = self._data_dir / prefix
            if not start_path.exists():
                return []
            if start_path.is_dir():
                return [
                    str(p.relative_to(self._data_dir))
                    for p in start_path.rglob("*")
                    if p.is_file()
                ]
            elif start_path.is_file():
                return [str(start_path.relative_to(self._data_dir))]
            return []

        return await asyncio.to_thread(_list_files)

    async def get_settings(self, scope: str) -> dict[str, Any]:
        """
        Retrieve all settings for a specific scope.

        Args:
            scope: The settings scope ('bundle', 'project', 'user')

        Returns:
            A dictionary of settings for that scope. Returns an empty dict
            if the settings file doesn't exist.
        """
        if scope not in ("bundle", "project", "user"):
            raise ValueError(f"Invalid settings scope: {scope}")

        file_path = self._get_path_for_scope(scope)
        key = str(file_path.relative_to(self._data_dir))

        settings = await self.get(key)
        return settings or {}

    async def save_settings(self, scope: str, settings: dict[str, Any]) -> None:
        """
        Save settings for a specific scope. This overwrites the entire file.

        Args:
            scope: The settings scope ('bundle', 'project', 'user')
            settings: A dictionary of settings to save for that scope.
        """
        if scope not in ("bundle", "project", "user"):
            raise ValueError(f"Invalid settings scope: {scope}")

        file_path = self._get_path_for_scope(scope)
        key = str(file_path.relative_to(self._data_dir))

        await self.set(key, settings)
