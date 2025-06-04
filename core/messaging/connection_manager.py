# core/messaging/connection_manager.py

import asyncio
from typing import Iterable

from fastapi import WebSocket

from core.bases.models import QiSession
from core.logger import get_logger

log = get_logger(__name__)


class QiConnectionManager:
    """
    Async-safe registry of active WebSocket connections (FastAPI flavour).

    All writes (register/unregister) are serialized under a single asyncio.Lock.
    Getters that need to “fan out” can take a bulk snapshot under the same lock,
    then send messages lock-free.

    Task code **must** call `unregister(session_id=...)` when a client disconnects;
    the manager never polls WebSocket.application_state directly.

    Each QiSession has:
      - `id`:              low-level unique ID (UUID) for this WebSocket connection
      - `logical_id`:      developer-provided key (e.g. “nuke-1234”) used for routing
      - `parent_logical_id`: optional logical_id of a parent session
      - `tags`:            metadata list (unused by this manager directly)
    """

    def __init__(self) -> None:
        # session_id → WebSocket
        self._sockets: dict[str, WebSocket] = {}

        # session_id → QiSession
        self._sessions: dict[str, QiSession] = {}

        # logical_id → session_id
        self._logical_to_session: dict[str, str] = {}

        # parent_logical_id → set of child logical_ids
        self._children: dict[str, set[str]] = {}

        # One lock protects all of the above
        self._lock = asyncio.Lock()

    async def register(self, *, socket: WebSocket, session: QiSession) -> None:
        """
        Register a new session-socket pair.

        If another session already exists with the same logical_id, that old
        session (and its descendants) are unregistered first.

        Args:
            socket:   the WebSocket instance for this session
            session:  a QiSession object, with fields (id, logical_id, parent_logical_id, tags)
        """
        async with self._lock:
            # If this logical_id is already in use, tear down the old one first
            previous_session_id = self._logical_to_session.get(session.logical_id)
            if previous_session_id:
                await self._unsafe_unregister(previous_session_id)

            # Now insert the new session
            self._sessions[session.id] = session
            self._sockets[session.id] = socket
            self._logical_to_session[session.logical_id] = session.id

            # If the new session has a parent, link it in the children map
            if session.parent_logical_id:
                self._children.setdefault(session.parent_logical_id, set()).add(
                    session.logical_id
                )

    async def unregister(self, *, session_id: str) -> None:
        """
        Unregister a session (identified by its low-level session_id).
        Also unregisters any child sessions (recursively).

        Args:
            session_id: the unique ID of the session to remove
        """
        async with self._lock:
            await self._unsafe_unregister(session_id)

    async def _unsafe_unregister(self, session_id: str) -> None:
        """
        (Called under lock) Remove the given session_id and all of its descendants.

        Uses a stack to avoid recursion depth issues. For each session popped:
          - remove from _sessions, _sockets, _logical_to_session
          - enqueue any child logical_ids for later teardown
          - schedule socket.close() asynchronously (outside the lock)
        """
        stack: list[str] = [session_id]

        while stack:
            current_session_id = stack.pop()
            current_session = self._sessions.pop(current_session_id, None)
            current_socket = self._sockets.pop(current_session_id, None)

            if current_session:
                logical = current_session.logical_id
                # Remove this logical_id → session_id mapping
                self._logical_to_session.pop(logical, None)

                # Find all children of this logical_id
                child_logicals = self._children.pop(logical, set())
                for child_logical in child_logicals:
                    child_session_id = self._logical_to_session.get(child_logical)
                    if child_session_id:
                        stack.append(child_session_id)

            if current_socket:
                # Schedule a “best-effort” close outside the lock
                asyncio.create_task(self._safe_close(current_socket))

    async def _safe_close(self, socket: WebSocket) -> None:
        """
        Best-effort WebSocket close; swallow any exceptions.

        Args:
            socket: the WebSocket to close
        """
        try:
            await socket.close()
        except Exception:
            log.exception("Error while closing WebSocket")

    # —————— SNAPSHOT HELPERS ——————

    async def snapshot_sockets(self) -> dict[str, WebSocket]:
        """
        Take a point-in-time snapshot of {session_id → WebSocket} under one lock.
        Callers can then iterate or filter without acquiring the lock again.

        Returns:
            A shallow copy of the internal _sockets dict.
        """
        async with self._lock:
            return dict(self._sockets)

    async def snapshot_sessions_by_logical(
        self, logical_ids: Iterable[str]
    ) -> dict[str, WebSocket]:
        """
        Take a snapshot of sockets for all sessions whose logical_id is in logical_ids.

        Returns:
            A dict mapping each matching session_id → WebSocket.
        """
        async with self._lock:
            result: dict[str, WebSocket] = {}
            for session_id, socket in self._sockets.items():
                session = self._sessions.get(session_id)
                if session and session.logical_id in logical_ids:
                    result[session_id] = socket
            return result

    # —————— LOCK-FREE “TRY” GETTERS ——————

    def try_get_socket(self, *, session_id: str) -> WebSocket | None:
        """
        Lock-free attempt to fetch a WebSocket by session_id.
        May return None if the session was just unregistered.

        Args:
            session_id: the unique low-level session ID

        Returns:
            The WebSocket if still registered, else None.
        """
        return self._sockets.get(session_id)

    def try_get_session(self, *, session_id: str) -> QiSession | None:
        """
        Lock-free attempt to fetch QiSession by session_id.
        May return None if the session was just unregistered.

        Args:
            session_id: the unique low-level session ID

        Returns:
            The QiSession object if still registered, else None.
        """
        return self._sessions.get(session_id)

    def get_children_logicals(self, *, logical_id: str) -> set[str]:
        """
        Return a **copy** of the set of child logical_ids of the given logical_id.
        Lock-free: may be stale if sessions change simultaneously.

        Args:
            logical_id: parent’s logical ID

        Returns:
            A set of child logical IDs (possibly empty).
        """
        return set(self._children.get(logical_id, set()))
