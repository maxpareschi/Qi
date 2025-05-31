# core/bus/connection_manager.py
import asyncio

from core.bases.models import QiConnection, QiSource, SourceKey
from core.logger import get_logger

log = get_logger(__name__)


class QiConnectionManager:
    """Async-safe registry of active WebSocket connections."""

    def __init__(self) -> None:
        # Primary storage
        self.by_id: dict[str, QiConnection] = {}

        # Indices - using regular dicts to avoid defaultdict memory leaks
        self.by_source: dict[SourceKey, set[str]] = {}
        self.by_source_id: dict[str, set[str]] = {}
        self.by_session: dict[str, set[str]] = {}
        self.by_addon: dict[str, set[str]] = {}
        self.by_window: dict[str, str] = {}  # one cid per window

        # Single async lock for mutators only
        self._async_lock = asyncio.Lock()

    # ------------------------------------------------------------------ register
    async def register(self, *, conn: QiConnection) -> None:
        if not conn.id or not conn.source:
            raise ValueError("QiConnection missing id/source")

        old_conn_to_close = None  # Collect old connection for closing outside lock

        async with self._async_lock:
            cid = conn.id

            if cid in self.by_id:
                log.warning(f"Connection {cid} already registered, skipping")
                return

            # Handle window collision atomically (no await inside lock)
            wid = conn.source.window_id
            if wid is not None:
                old_cid = self.by_window.get(wid)
                if old_cid and old_cid in self.by_id:
                    log.warning(f"Replacing connection {old_cid} on window {wid}")
                    old_conn_to_close = self.by_id[old_cid]  # Collect for closing
                    self._drop_indices(old_cid)

            # Main store
            self.by_id[cid] = conn

            # Indices - using setdefault to avoid defaultdict memory leaks
            self.by_source.setdefault(conn.source.key, set()).add(cid)
            self.by_source_id.setdefault(conn.source.id, set()).add(cid)
            self.by_session.setdefault(conn.source.session_id, set()).add(cid)
            self.by_addon.setdefault(conn.source.addon, set()).add(cid)
            if wid is not None:
                self.by_window[wid] = cid

            if __debug__:
                self._assert_consistency()

        # Close old socket outside the lock to avoid blocking
        if old_conn_to_close:
            await old_conn_to_close.socket.close()

    # ---------------------------------------------------------------- unregister
    async def unregister(self, *, connection_id: str) -> None:
        if not connection_id:
            return
        async with self._async_lock:
            self._drop_indices(connection_id)
            if __debug__:
                self._assert_consistency()

    # ---------------------------------------------------------------- closers
    async def close_all(self) -> None:
        async with self._async_lock:
            connections = list(self.by_id.values())
        close_tasks = [conn.socket.close() for conn in connections]
        await asyncio.gather(*close_tasks, return_exceptions=True)

    async def close_by_id(self, *, connection_id: str) -> None:
        if not connection_id:
            return

        async with self._async_lock:
            conn = self.by_id.get(connection_id)

        if conn:
            await conn.socket.close()

    async def close_by_source(self, *, source: QiSource) -> None:
        if not source:
            return

        async with self._async_lock:
            cids = self.by_source.get(source.key, set()).copy()
            connections = [self.by_id[cid] for cid in cids if cid in self.by_id]

        await asyncio.gather(
            *(c.socket.close() for c in connections), return_exceptions=True
        )

    async def close_by_session(self, *, session_id: str) -> None:
        if not session_id:
            return

        async with self._async_lock:
            cids = self.by_session.get(session_id, set()).copy()
            connections = [self.by_id[cid] for cid in cids if cid in self.by_id]

        await asyncio.gather(
            *(c.socket.close() for c in connections), return_exceptions=True
        )

    async def close_by_addon(self, *, addon: str) -> None:
        if not addon:
            return

        async with self._async_lock:
            cids = self.by_addon.get(addon, set()).copy()
            connections = [self.by_id[cid] for cid in cids if cid in self.by_id]

        await asyncio.gather(
            *(c.socket.close() for c in connections), return_exceptions=True
        )

    # ---------------------------------------------------------------- lock-free getters (max performance)
    def get_by_id(self, *, connection_id: str) -> QiConnection | None:
        """Lock-free getter - returns immutable connection object."""
        if not connection_id:
            return None
        return self.by_id.get(connection_id)

    def get_by_source(self, *, source: QiSource) -> list[QiConnection]:
        """Lock-free getter with graceful handling of concurrent modifications."""
        if not source:
            return []
        try:
            cids = self.by_source.get(source.key, set()).copy()
            return [self.by_id[cid] for cid in cids if cid in self.by_id]
        except (KeyError, RuntimeError):
            # Rare race condition during concurrent unregister - return empty
            return []

    def get_by_source_id(self, *, source_id: str) -> list[QiConnection]:
        """Lock-free getter with graceful handling of concurrent modifications."""
        if not source_id:
            return []
        try:
            cids = self.by_source_id.get(source_id, set()).copy()
            return [self.by_id[cid] for cid in cids if cid in self.by_id]
        except (KeyError, RuntimeError):
            # Rare race condition during concurrent unregister - return empty
            return []

    def get_by_session(self, *, session_id: str) -> list[QiConnection]:
        """Lock-free getter with graceful handling of concurrent modifications."""
        if not session_id:
            return []
        try:
            cids = self.by_session.get(session_id, set()).copy()
            return [self.by_id[cid] for cid in cids if cid in self.by_id]
        except (KeyError, RuntimeError):
            # Rare race condition during concurrent unregister - return empty
            return []

    def get_by_addon(self, *, addon: str) -> list[QiConnection]:
        """Lock-free getter with graceful handling of concurrent modifications."""
        if not addon:
            return []
        try:
            cids = self.by_addon.get(addon, set()).copy()
            return [self.by_id[cid] for cid in cids if cid in self.by_id]
        except (KeyError, RuntimeError):
            # Rare race condition during concurrent unregister - return empty
            return []

    def get_by_window(self, *, window_id: str) -> QiConnection | None:
        """Lock-free getter - returns immutable connection object."""
        if not window_id:
            return None
        cid = self.by_window.get(window_id)
        return self.by_id.get(cid) if cid else None

    # ---------------------------------------------------------------- internal
    def _drop_indices(self, cid: str) -> None:
        """Remove cid from every index; internal, lock must be held."""
        conn = self.by_id.pop(cid, None)
        if not conn:
            return

        # Remove from each index and clean up empty sets to prevent memory leaks
        source_cids = self.by_source.get(conn.source.key)
        if source_cids:
            source_cids.discard(cid)
            if not source_cids:
                self.by_source.pop(conn.source.key)

        source_id_cids = self.by_source_id.get(conn.source.id)
        if source_id_cids:
            source_id_cids.discard(cid)
            if not source_id_cids:
                self.by_source_id.pop(conn.source.id)

        session_cids = self.by_session.get(conn.source.session_id)
        if session_cids:
            session_cids.discard(cid)
            if not session_cids:
                self.by_session.pop(conn.source.session_id)

        addon_cids = self.by_addon.get(conn.source.addon)
        if addon_cids:
            addon_cids.discard(cid)
            if not addon_cids:
                self.by_addon.pop(conn.source.addon)

        if conn.source.window_id is not None:
            self.by_window.pop(conn.source.window_id, None)

    def _assert_consistency(self) -> None:
        """Debug-only cross-check of all indices; lock already held."""
        # Forward check: every connection in by_id exists in all relevant indices
        for cid, conn in self.by_id.items():
            assert cid in self.by_source.get(conn.source.key, set())
            assert cid in self.by_source_id.get(conn.source.id, set())
            assert cid in self.by_session.get(conn.source.session_id, set())
            assert cid in self.by_addon.get(conn.source.addon, set())
            if conn.source.window_id is not None:
                assert self.by_window.get(conn.source.window_id) == cid

        # Reverse check: every indexed cid exists in by_id
        for cids in self.by_source.values():
            for cid in cids:
                assert cid in self.by_id, f"Stale {cid} in by_source"
        for cids in self.by_source_id.values():
            for cid in cids:
                assert cid in self.by_id, f"Stale {cid} in by_source_id"
        for cids in self.by_session.values():
            for cid in cids:
                assert cid in self.by_id, f"Stale {cid} in by_session"
        for cids in self.by_addon.values():
            for cid in cids:
                assert cid in self.by_id, f"Stale {cid} in by_addon"
        for cid in self.by_window.values():
            assert cid in self.by_id, f"Stale {cid} in by_window"

    # ---------------------------------------------------------------- misc
    async def clear(self) -> None:
        """Close sockets then clear all indices."""
        await self.close_all()
        async with self._async_lock:
            self.by_id.clear()
            self.by_source.clear()
            self.by_source_id.clear()
            self.by_session.clear()
            self.by_addon.clear()
            self.by_window.clear()
