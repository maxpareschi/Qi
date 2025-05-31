# core/bus/connection_manager.py

import asyncio
from collections import defaultdict

from core.bases.models import QiConnection, QiSource, SourceKey
from core.logger import get_logger

log = get_logger(__name__)


class QiConnectionManager:
    """
    Async-safe registry of QiConnection objects, indexed by various keys:

    • Stores active connections in by_id.
    • Indexes connection IDs by source.key, source.id, session, addon, and window.
    • Provides async-safe register/unregister/close operations.
    """

    def __init__(self) -> None:
        # connection_id → QiConnection
        self.by_id: dict[str, QiConnection] = {}

        # source_key → set of connection_ids
        self.by_source: dict[SourceKey, set[str]] = defaultdict(set)

        # source.id → set of connection_ids
        self.by_source_id: dict[str, set[str]] = defaultdict(set)

        # session_id → set of connection_ids
        self.by_session: dict[str, set[str]] = defaultdict(set)

        # addon → set of connection_ids
        self.by_addon: dict[str, set[str]] = defaultdict(set)

        # window_id → connection_id (assumes at most one connection per window)
        self.by_window: dict[str, str] = {}

        # Lock to guard all mutations and lookups
        self._lock = asyncio.Lock()

    async def register(self, conn: QiConnection) -> None:
        """
        Register a new QiConnection. Index it under all relevant maps.
        Must be called when a WebSocket is accepted (e.g. in ws_endpoint).
        """
        async with self._lock:
            cid = conn.id

            # 1) Store in by_id
            self.by_id[cid] = conn

            # 2) Index by (addon, session_id, window_id)
            self.by_source[conn.source.key].add(cid)

            # 3) Index by source.id
            self.by_source_id[conn.source.id].add(cid)

            # 4) Index by session_id
            self.by_session[conn.source.session_id].add(cid)

            # 5) Index by addon
            self.by_addon[conn.source.addon].add(cid)

            # 6) If window_id is set, store a single mapping
            if conn.source.window_id is not None:
                self.by_window[conn.source.window_id] = cid

            # Debug‐only consistency check
            if __debug__:
                self._assert_consistency()

    async def unregister(self, *, connection_id: str) -> None:
        """
        Unregister (remove) a single QiConnection by its ID.
        This removes it from all internal indices.
        """
        async with self._lock:
            conn = self.by_id.pop(connection_id, None)
            if not conn:
                return

            # Remove from by_source
            src_key = conn.source.key
            self.by_source[src_key].discard(connection_id)
            if not self.by_source[src_key]:
                self.by_source.pop(src_key, None)

            # Remove from by_source_id
            src_id = conn.source.id
            self.by_source_id[src_id].discard(connection_id)
            if not self.by_source_id[src_id]:
                self.by_source_id.pop(src_id, None)

            # Remove from by_session
            sess = conn.source.session_id
            self.by_session[sess].discard(connection_id)
            if not self.by_session[sess]:
                self.by_session.pop(sess, None)

            # Remove from by_addon
            addon = conn.source.addon
            self.by_addon[addon].discard(connection_id)
            if not self.by_addon[addon]:
                self.by_addon.pop(addon, None)

            # Remove from by_window (if set)
            if conn.source.window_id is not None:
                self.by_window.pop(conn.source.window_id, None)

            # Debug‐only consistency check
            if __debug__:
                self._assert_consistency()

    async def close_all(self) -> None:
        """
        Close every WebSocket in by_id. Returns immediately once all close
        calls have been scheduled; any exceptions are collected and ignored.
        """
        async with self._lock:
            close_tasks = [c.socket.close() for c in self.by_id.values()]
        # Release lock before awaiting so that other tasks can proceed
        await asyncio.gather(*close_tasks, return_exceptions=True)

    async def close_by_id(self, *, connection_id: str) -> None:
        """
        Close a single WebSocket by its connection_id.
        """
        async with self._lock:
            conn = self.by_id.get(connection_id)
        if conn:
            await conn.socket.close()

    async def close_by_source(self, *, source: QiSource) -> None:
        """
        Close all WebSockets that match a given source.key (addon, session_id, window_id).
        """
        async with self._lock:
            cids = list(self.by_source.get(source.key, []))
        # Schedule closes outside the lock
        close_tasks = []
        for cid in cids:
            conn = self.by_id.get(cid)
            if conn:
                close_tasks.append(conn.socket.close())
        await asyncio.gather(*close_tasks, return_exceptions=True)

    def get_by_id(self, connection_id: str) -> QiConnection | None:
        """
        Return a QiConnection by its ID, or None if not found.
        """
        return self.by_id.get(connection_id)

    def get_by_source_id(self, source_id: str) -> list[QiConnection]:
        """
        Return all QiConnections matching a given source.id.
        """
        return [self.by_id[cid] for cid in self.by_source_id.get(source_id, [])]

    def get_by_session(self, session_id: str) -> list[QiConnection]:
        """
        Return all QiConnections for a given session_id.
        """
        return [self.by_id[cid] for cid in self.by_session.get(session_id, [])]

    def get_by_addon(self, addon: str) -> list[QiConnection]:
        """
        Return all QiConnections for a given addon.
        """
        return [self.by_id[cid] for cid in self.by_addon.get(addon, [])]

    def get_by_window(self, window_id: str) -> QiConnection | None:
        """
        Return the single QiConnection for a window_id (if present).
        """
        cid = self.by_window.get(window_id)
        return self.by_id.get(cid) if cid is not None else None

    def _assert_consistency(self) -> None:
        """
        Debug-only assertion that validates forward/reverse mapping consistency
        across all indices. Called under `if __debug__` to catch any drift.
        """
        # 1) Every connection_id in by_id must appear in all relevant indices
        for cid, conn in self.by_id.items():
            # by_source
            assert cid in self.by_source.get(conn.source.key, set()), (
                f"Connection {cid} missing from by_source[{conn.source.key!r}]"
            )
            # by_source_id
            assert cid in self.by_source_id.get(conn.source.id, set()), (
                f"Connection {cid} missing from by_source_id[{conn.source.id!r}]"
            )
            # by_session
            assert cid in self.by_session.get(conn.source.session_id, set()), (
                f"Connection {cid} missing from by_session[{conn.source.session_id!r}]"
            )
            # by_addon
            assert cid in self.by_addon.get(conn.source.addon, set()), (
                f"Connection {cid} missing from by_addon[{conn.source.addon!r}]"
            )
            # by_window (if window_id is set)
            if conn.source.window_id is not None:
                assert self.by_window.get(conn.source.window_id) == cid, (
                    f"Connection {cid} incorrect or missing in by_window[{conn.source.window_id!r}]"
                )

        # 2) Every index entry must map back to a valid by_id
        for key, cids in self.by_source.items():
            for cid in cids:
                assert cid in self.by_id, f"Stale {cid} in by_source[{key!r}]"
        for key, cids in self.by_source_id.items():
            for cid in cids:
                assert cid in self.by_id, f"Stale {cid} in by_source_id[{key!r}]"
        for key, cids in self.by_session.items():
            for cid in cids:
                assert cid in self.by_id, f"Stale {cid} in by_session[{key!r}]"
        for key, cids in self.by_addon.items():
            for cid in cids:
                assert cid in self.by_id, f"Stale {cid} in by_addon[{key!r}]"
        for key, cid in self.by_window.items():
            assert cid in self.by_id, f"Stale {cid} in by_window[{key!r}]"

    async def clear(self) -> None:
        """
        Purge every connection and index.
        """
        async with self._lock:
            self.by_id.clear()
            self.by_source.clear()
            self.by_source_id.clear()
            self.by_session.clear()
            self.by_addon.clear()
            self.by_window.clear()

            # Final consistency sweep (trivially passes if all containers are empty)
            if __debug__:
                self._assert_consistency()
