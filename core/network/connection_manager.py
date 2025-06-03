import asyncio
from typing import Final

from fastapi import WebSocket

from core.bases.models import QiSession
from core.logger import get_logger

log = get_logger(__name__)


class QiConnectionManager:
    """
    Manages active WebSocket connections and their associated QiSession objects.

    This class provides a registry for:
    - Mapping session_id to WebSocket objects.
    - Mapping logical_id to the current session_id (for hot-reloading/reconnection).
    - Tracking parent-child relationships between logical_ids for hierarchical cleanup.
    All operations modifying the internal state are protected by an asyncio.Lock.
    """

    def __init__(self) -> None:
        """Initializes the QiConnectionManager with empty registries and a new lock."""
        self._sockets: dict[str, WebSocket] = {}
        self._sessions: dict[str, QiSession] = {}
        self._logical_to_session: dict[str, str] = {}
        self._children: dict[str, set[str]] = {}
        self._lock: Final = asyncio.Lock()

    async def register(self, socket: WebSocket, session: QiSession) -> None:
        """
        Registers a new WebSocket connection and its associated QiSession.

        This method is thread-safe. If a session with the same logical_id already
        exists, the old session will be unregistered before the new one is registered.

        Args:
            socket: The FastAPI WebSocket object for the connection.
            session: The QiSession object containing session metadata.
        """
        async with self._lock:
            await self._unsafe_register(socket, session)

    async def unregister(self, session_id: str) -> None:
        """
        Unregisters a session by its session_id.

        This involves closing its WebSocket, removing it from all internal registries,
        and recursively unregistering any child sessions.
        This method is thread-safe.

        Args:
            session_id: The unique ID of the session to unregister.
        """
        async with self._lock:
            await self._unsafe_unregister(session_id)

    async def close_all(self) -> None:
        """Closes all currently registered WebSocket connections and unregisters all sessions.
        This method is thread-safe.
        """
        async with self._lock:
            for sid in list(self._sockets):  # Iterate over a copy of keys
                await self._unsafe_unregister(sid)

    async def get_socket(self, session_id: str) -> WebSocket | None:
        """
        Retrieves the WebSocket object for a given session_id in a thread-safe manner.

        Args:
            session_id: The ID of the session whose WebSocket is requested.

        Returns:
            The WebSocket object if found, otherwise None.
        """
        async with self._lock:
            return self._get_socket(session_id)

    async def get_live_session_id(self, logical_id: str) -> str | None:
        """
        Retrieves the current (live) session_id for a given logical_id.
        This is useful for finding the active session for a known logical client identifier.
        This method is thread-safe.

        Args:
            logical_id: The logical identifier of the session.

        Returns:
            The current session_id if a live session exists for this logical_id, otherwise None.
        """
        async with self._lock:
            return self._get_live_session_id(logical_id)

    def _get_socket(self, session_id: str) -> WebSocket | None:
        """
        Fast, unsafe getter for a WebSocket by session_id.
        Assumes the caller holds the lock or guarantees no concurrent modifications.

        Args:
            session_id: The ID of the session.

        Returns:
            The WebSocket object or None.
        """
        return self._sockets.get(session_id)

    def _get_live_session_id(self, logical_id: str) -> str | None:
        """
        Fast, unsafe getter for a live session_id by logical_id.
        Assumes the caller holds the lock or guarantees no concurrent modifications.

        Args:
            logical_id: The logical identifier of the session.

        Returns:
            The current session_id or None.
        """
        return self._logical_to_session.get(logical_id)

    async def _unsafe_register(
        self, socket: WebSocket, session: QiSession, visited: set[str] = set()
    ) -> None:
        """
        Internal, unsafe method to register a session. Assumes lock is held.
        Handles replacement of existing sessions for a given logical_id.

        Args:
            socket: The WebSocket object.
            session: The QiSession data.
            visited: A set of visited session IDs to prevent cycles during potential
                     recursive calls to unregister (primarily from hot-reloading).
        """
        if old_socket := self._sockets.pop(session.id, None):
            await self._safe_close(old_socket)

        if previous_session_id := self._logical_to_session.get(session.logical_id):
            if previous_session_id not in visited:
                # Pass a copy of visited for safety in recursive calls
                await self._unsafe_unregister(
                    previous_session_id, visited=visited.copy()
                )
            else:
                log.warning(
                    f"Skipping unregister for {previous_session_id} in _unsafe_register due to potential cycle."
                )

        self._sockets[session.id] = socket
        self._sessions[session.id] = session
        self._logical_to_session[session.logical_id] = session.id
        if session.parent_logical_id:
            self._children.setdefault(session.parent_logical_id, set()).add(
                session.logical_id
            )

    async def _unsafe_unregister(
        self, session_id: str, visited: set[str] = set()
    ) -> None:
        """
        Internal, unsafe method to unregister a session. Assumes lock is held.
        Recursively unregisters child sessions and performs cycle detection.

        Args:
            session_id: The ID of the session to unregister.
            visited: A set of visited session IDs to prevent infinite recursion in case of cycles.
        """
        if session_id in visited:
            log.warning(
                f"Cycle detected during unregister for session {session_id}. Aborting further recursion for this path."
            )
            return
        visited.add(session_id)

        socket = self._sockets.pop(session_id, None)
        session = self._sessions.pop(session_id, None)
        if not session:
            return

        self._logical_to_session.pop(session.logical_id, None)

        child_logical_ids = self._children.pop(session.logical_id, set())
        for child_logical in child_logical_ids:
            if child_session_id := self._logical_to_session.get(child_logical):
                await self._unsafe_unregister(child_session_id, visited.copy())

        if socket:
            await self._safe_close(socket)

    async def _safe_close(self, socket: WebSocket) -> None:
        """
        Safely closes a WebSocket connection, ignoring exceptions if already closed.

        Args:
            socket: The WebSocket to close.
        """
        try:
            await socket.close()
        except Exception as e:  # noqa: BLE001
            log.debug(f"Socket already closed or closing: {e}")

    async def get_all_logical_ids(self) -> list[str]:
        """
        Retrieves a list of all currently active logical_ids in a thread-safe manner.

        Returns:
            A list of unique logical_ids.
        """
        async with self._lock:
            return list(self._logical_to_session.keys())

    async def get_multiple_session_ids(self, logical_ids: list[str]) -> list[str]:
        """
        Retrieves current (live) session_ids for a given list of logical_ids.
        This method is thread-safe.

        Args:
            logical_ids: A list of logical identifiers.

        Returns:
            A list of corresponding live session_ids. If a logical_id is not active,
            it's omitted from the result.
        """
        async with self._lock:
            result = []
            for logical_id in logical_ids:
                session_id = self._logical_to_session.get(logical_id)
                if session_id is not None:
                    result.append(session_id)
            return result
