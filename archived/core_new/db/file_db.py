"""
File Database Adapter for Qi.

This module provides a file-based database adapter using JSON files.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar

from core_new.db.adapters import QiStorageAdapter, StorageError
from core_new.logger import get_logger

log = get_logger("db.file_db")

T = TypeVar("T")


class JsonFileDbAdapter(QiStorageAdapter[Dict[str, Any]]):
    """
    JSON file-based database adapter.

    This adapter stores data in JSON files, with one file per collection.
    It includes an in-memory caching layer to improve performance for
    frequently accessed data, with TTL and file modification checks.
    """

    def __init__(self, base_dir: str):
        """
        Initialize the adapter with a base directory for data files.

        Args:
            base_dir: The base directory for data files.
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._locks: Dict[Path, asyncio.Lock] = {}
        self._master_lock = asyncio.Lock()  # To protect access to _locks

        # Cache for loaded data with timestamps
        self._cache: dict[str, dict[str, Any]] = {}
        # "mtime" is the file's modification time (from os.path.getmtime)
        # "load_time" is the monotonic time the cache entry was created (from time.monotonic())
        self._cache_ttl = 5.0  # seconds
        log.info(f"JsonFileDbAdapter initialized with data directory: {self.base_dir}")

    async def _get_lock(self, file_path: Path) -> asyncio.Lock:
        """Get or create a lock for a specific file path."""
        async with self._master_lock:
            if file_path not in self._locks:
                self._locks[file_path] = asyncio.Lock()
            return self._locks[file_path]

    def _get_collection_path(self, collection: str) -> Path:
        """
        Get the path to a collection file.

        Args:
            collection: The collection name.

        Returns:
            The path to the collection file.
        """
        return self.base_dir / f"{collection}.json"

    def _is_cache_valid(self, collection: str, file_path: Path) -> bool:
        """
        Check if the cached data for a collection is still valid.
        """
        if collection not in self._cache:
            return False

        cache_entry = self._cache[collection]
        load_time = cache_entry.get("load_time", 0)

        # 1. Check if cache is fresh based on TTL
        if time.monotonic() - load_time < self._cache_ttl:
            return True

        # 2. TTL expired, check if file on disk has changed
        try:
            current_mtime = file_path.stat().st_mtime
            cached_mtime = cache_entry.get("mtime", 0)
            if current_mtime > cached_mtime:
                log.debug(
                    f"Cache invalidated for '{collection}': file modified on disk."
                )
                del self._cache[collection]
                return False
        except (FileNotFoundError, PermissionError):
            # If we can't stat, invalidate cache to be safe
            if collection in self._cache:
                del self._cache[collection]
            return False

        # 3. TTL expired but file not modified. Re-validate by re-reading.
        return False

    async def _read_collection(self, collection: str) -> Dict[str, Any]:
        """
        Read a collection from disk, using cache if possible.
        """
        path = self._get_collection_path(collection)
        lock = await self._get_lock(path)

        async with lock:
            if self._is_cache_valid(collection, path):
                log.debug(f"Cache hit for collection '{collection}'")
                return self._cache[collection].get("data", {})

            if not await asyncio.to_thread(path.is_file):
                return {}

            try:
                mtime = (await asyncio.to_thread(path.stat)).st_mtime

                def _read_file():
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)

                data = await asyncio.to_thread(_read_file)

                self._cache[collection] = {
                    "data": data,
                    "mtime": mtime,
                    "load_time": time.monotonic(),
                }
                log.debug(f"Cache miss for '{collection}', loaded from disk.")
                return data
            except (json.JSONDecodeError, IOError, FileNotFoundError) as e:
                log.error(f"Error reading or decoding file {path}: {e}")
                if collection in self._cache:
                    del self._cache[collection]
                raise StorageError(
                    f"Failed to read collection '{collection}': {e}"
                ) from e

    async def _write_collection(self, collection: str, data: Dict[str, Any]) -> None:
        """
        Write a collection to disk.

        Args:
            collection: The collection name.
            data: The collection data.
        """
        path = self._get_collection_path(collection)
        lock = await self._get_lock(path)
        try:
            async with lock:
                temp_file_path = path.with_suffix(f"{path.suffix}.tmp")

                def _write_file():
                    with open(temp_file_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    os.replace(temp_file_path, path)

                await asyncio.to_thread(_write_file)
                mtime = (await asyncio.to_thread(path.stat)).st_mtime
                self._cache[collection] = {
                    "data": data,
                    "mtime": mtime,
                    "load_time": time.monotonic(),
                }
        except (TypeError, IOError) as e:
            log.error(f"Error writing collection {collection}: {e}")
            raise StorageError(f"Failed to write collection '{collection}': {e}") from e

    async def get(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document from a collection by ID.

        Args:
            collection: The collection name.
            doc_id: The document ID.

        Returns:
            The document, or None if not found.
        """
        data = await self._read_collection(collection)
        return data.get(doc_id)

    async def get_all(self, collection: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all documents from a collection.

        Args:
            collection: The collection name.

        Returns:
            A dictionary of documents, keyed by ID.
        """
        return await self._read_collection(collection)

    async def put(self, collection: str, doc_id: str, document: Dict[str, Any]) -> None:
        """
        Put a document into a collection.

        Args:
            collection: The collection name.
            doc_id: The document ID.
            document: The document data.
        """
        data = await self._read_collection(collection)
        data[doc_id] = document
        await self._write_collection(collection, data)

    async def delete(self, collection: str, doc_id: str) -> bool:
        """
        Delete a document from a collection.

        Args:
            collection: The collection name.
            doc_id: The document ID.

        Returns:
            True if the document was deleted, False if it was not found.
        """
        data = await self._read_collection(collection)
        if doc_id not in data:
            return False

        del data[doc_id]
        await self._write_collection(collection, data)
        return True

    async def query(
        self, collection: str, query_fn: callable[[Dict[str, Any]], bool]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Query a collection using a filter function.

        Args:
            collection: The collection name.
            query_fn: A function that takes a document and returns True if it matches.

        Returns:
            A dictionary of matching documents, keyed by ID.
        """
        data = await self._read_collection(collection)
        return {id: doc for id, doc in data.items() if query_fn(doc)}

    async def list_collections(self) -> List[str]:
        """
        List all collections.

        Returns:
            A list of collection names.
        """
        collections = []
        for path in self.base_dir.glob("*.json"):
            collections.append(path.stem)
        return collections
