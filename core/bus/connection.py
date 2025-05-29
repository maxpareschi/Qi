import asyncio
from collections import defaultdict
from dataclasses import (
    field,
    # dataclass,
)
from uuid import uuid4

from fastapi import WebSocket
from pydantic.dataclasses import dataclass

ADDON = "addon"
SESSION = "session"
WINDOW = "window"


@dataclass
class QiConnectionSource:
    """Source of a connection to the message bus."""

    source_id: str
    addon: str
    session_id: str
    window_id: str | None = None


@dataclass
class QiConnection:
    """A connection to the message bus."""

    connection_id: str = field(default_factory=lambda: str(uuid4()))
    socket: WebSocket
    source: QiConnectionSource


@dataclass
class QiConnectionManager:
    """Manager for connections to the message bus.
    This class is used to store connections between the Qi managed processes and to retrieve them.
    It mantains an index of connections by ID, session, addon and window
    in its internal dictionaries.
    """

    by_id: defaultdict[str, QiConnection] = field(
        default_factory=lambda: defaultdict(QiConnection)
    )
    by_source: defaultdict[tuple[str, str, str | None], set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    by_source_id: defaultdict[str, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    by_session: defaultdict[str, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    by_addon: defaultdict[str, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    by_window: defaultdict[str, str] = field(default_factory=lambda: defaultdict(str))

    def register(self, connection: QiConnection):
        """Register a connection to the message bus."""

        self.by_id[connection.connection_id] = connection
        self.by_source[
            (
                connection.source.addon,
                connection.source.session_id,
                connection.source.window_id,
            )
        ].add(connection.connection_id)
        self.by_source_id[connection.source.source_id].add(connection.connection_id)
        self.by_session[connection.source.session_id].add(connection.connection_id)
        self.by_addon[connection.source.addon].add(connection.connection_id)
        if connection.source.window_id:
            self.by_window[connection.source.window_id] = connection.connection_id

    def unregister(self, connection: QiConnection):
        """Unregister a connection from the message bus."""

        self.by_id.pop(connection.connection_id, None)
        self.by_source[
            (
                connection.source.addon,
                connection.source.session_id,
                connection.source.window_id,
            )
        ].discard(connection.connection_id)
        self.by_source_id[connection.source.source_id].discard(connection.connection_id)
        self.by_session[connection.source.session_id].discard(connection.connection_id)
        self.by_addon[connection.source.addon].discard(connection.connection_id)
        if connection.source.window_id:
            self.by_window.pop(connection.source.window_id, None)

    def clear(self) -> None:
        """Clear all connections."""

        self.by_id.clear()
        self.by_session.clear()
        self.by_addon.clear()
        self.by_window.clear()

    def get_by_id(self, connection_id: str) -> QiConnection | None:
        """Return a connection by its ID."""

        return self.by_id.get(connection_id, None)

    def get_by_source_id(self, source_id: str) -> list[QiConnection]:
        """Return all connections for a source ID."""

        return [
            self.get_by_id(conn_id) for conn_id in self.by_source_id.get(source_id, [])
        ]

    def get_by_session(self, session_id: str) -> list[QiConnection]:
        """Return all connections for a session."""

        return [
            self.get_by_id(conn_id) for conn_id in self.by_session.get(session_id, [])
        ]

    def get_by_addon(self, addon: str) -> list[QiConnection]:
        """Return all connections for an addon."""

        return [self.get_by_id(conn_id) for conn_id in self.by_addon.get(addon, [])]

    def get_by_window(self, window_id: str) -> list[QiConnection]:
        """Return a connection by its window ID."""

        return [
            self.get_by_id(conn_id) for conn_id in self.by_window.get(window_id, [])
        ]

    def get_by_source(self, source: QiConnectionSource) -> list[QiConnection]:
        """Return all connections for a source."""

        return self.by_source.get(
            (source.addon, source.session_id, source.window_id), []
        )

    def infer_by_source(self, source: QiConnectionSource) -> list[QiConnection]:
        """Return all connections for a source."""

        if source.window_id:
            connections = self.get_by_window(source.window_id)
        elif source.session_id:
            connections = self.get_by_session(source.session_id)
        elif source.addon:
            connections = self.get_by_addon(source.addon)
        else:
            connections = self.get_by_source(source)

        return connections

    async def close_all(self) -> None:
        """Close all connections."""

        await asyncio.gather(
            [conn.socket.close() for conn in self.by_id.values()],
            return_exceptions=True,
        )

    async def close_by_id(self, connection_id: str) -> None:
        """Close a connection by its ID."""

        conn = self.get_by_id(connection_id)
        if conn:
            await conn.socket.close()

    async def close_by_source(self, source: QiConnectionSource) -> None:
        """Close all connections for a source."""

        if source.window_id:
            connections = self.get_by_window(source.window_id)
        else:
            connections = self.get_by_session(source.session_id)

        await asyncio.gather(
            [conn.socket.close() for conn in connections],
            return_exceptions=True,
        )
