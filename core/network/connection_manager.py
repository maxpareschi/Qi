import asyncio
from typing import Final

from fastapi import WebSocket

from core.bases.models import QiSession
from core.logger import get_logger

log = get_logger(__name__)


class QiConnectionManager:
    """
    Transport registry.

    • session_id → WebSocket
    • logical_id → *current* session_id
    • parent_logical_id → {child logical ids}
    """

    def __init__(self) -> None:
        self._sockets: dict[str, WebSocket] = {}
        self._sessions: dict[str, QiSession] = {}
        self._logical_to_session: dict[str, str] = {}
        self._children: dict[str, set[str]] = {}
        self._lock: Final = asyncio.Lock()

    async def register(self, socket: WebSocket, session: QiSession) -> None:
        async with self._lock:
            await self._unsafe_register(socket, session)

    async def unregister(self, session_id: str) -> None:
        async with self._lock:
            await self._unsafe_unregister(session_id)

    async def close_all(self) -> None:
        async with self._lock:
            for sid in list(self._sockets):
                await self._unsafe_unregister(sid)

    async def get_socket(self, session_id: str) -> WebSocket | None:
        """Thread-safe socket getter"""
        async with self._lock:
            return self._get_socket(session_id)

    async def get_live_session_id(self, logical_id: str) -> str | None:
        """Thread-safe session ID getter"""
        async with self._lock:
            return self._get_live_session_id(logical_id)

    def _get_socket(self, session_id: str) -> WebSocket | None:
        """Fast unsafe getter - use only when you know no concurrent modifications"""
        return self._sockets.get(session_id)

    def _get_live_session_id(self, logical_id: str) -> str | None:
        """Fast unsafe getter - use only when you know no concurrent modifications"""
        return self._logical_to_session.get(logical_id)

    async def _unsafe_register(self, socket: WebSocket, session: QiSession) -> None:
        if old_socket := self._sockets.pop(session.id, None):
            await self._safe_close(old_socket)

        # hot-reload: move logical_id
        if previous_session := self._logical_to_session.get(session.logical_id):
            await self._unsafe_unregister(previous_session)

        self._sockets[session.id] = socket
        self._sessions[session.id] = session
        self._logical_to_session[session.logical_id] = session.id
        if session.parent_logical_id:
            self._children.setdefault(session.parent_logical_id, set()).add(
                session.logical_id
            )

    async def _unsafe_unregister(self, session_id: str) -> None:
        socket = self._sockets.pop(session_id, None)
        session = self._sessions.pop(session_id, None)
        if not session:
            return

        self._logical_to_session.pop(session.logical_id, None)

        # recurse into live children - using safe local lookup
        child_logical_ids = self._children.pop(session.logical_id, set())
        for child_logical in child_logical_ids:
            if child_session_id := self._logical_to_session.get(child_logical):
                await self._unsafe_unregister(child_session_id)

        if socket:
            await self._safe_close(socket)

    async def _safe_close(self, socket: WebSocket) -> None:
        try:
            await socket.close()
        except Exception as e:  # noqa: BLE001
            log.debug(f"Socket already closed or closing: {e}")

    async def get_all_logical_ids(self) -> list[str]:
        """Get all logical IDs safely"""
        async with self._lock:
            return list(self._logical_to_session.keys())

    async def get_multiple_session_ids(self, logical_ids: list[str]) -> list[str]:
        """Get multiple session IDs safely"""
        async with self._lock:
            result = []
            for logical_id in logical_ids:
                session_id = self._logical_to_session.get(logical_id)
                if session_id is not None:
                    result.append(session_id)
            return result
