import asyncio
import uuid
from typing import Callable

from fastapi import WebSocket

from core.bus.connection import (
    QiConnection,
    QiConnectionManager,
    QiConnectionSource,
)
from core.bus.handler import Handler, QiHandlerManager
from core.bus.message import QiMessageManager
from core.logger import get_logger

log = get_logger(__name__)


class QiMessageBusSingletonMeta(type):
    """Singleton metaclass for the QiMessageBus.
    This metaclass ensures that only one instance of the QiMessageBus exists.
    """

    _instance: "QiMessageBus|None" = None

    def __call__(cls, *a, **kw):
        if cls._instance is None:
            cls._instance = super().__call__(*a, **kw)
        return cls._instance


class QiMessageBus(metaclass=QiMessageBusSingletonMeta):
    """Main message bus class.
    This class is a singleton that manages the message bus and its registries.

    The QiMessageBus is used to send messages between different parts of the system.
    It uses websockets as a primary transport, but can be extended to other transports
    since it follows a defined schema for messages using dataclasses.
    The message schema is defined in the core.bus.message module, and its data layout
    makes it easy to infer routing rules.

    Main components:
    - self._handlers: QiHandlerManager for handlers for messages.
    - self._connections: QiConnectionRegistry for WebSocket connections to the message bus.
    - self._messages: QiMessageManager for messages sent through the message bus.

    Responsibilities:
    - Managing the registries for handlers, connections and messages.
    - Receiving, sending and routing messages to the correct handlers.
    - Sending targeted replies to the correct handlers.
    - Opening and closing connections to the message bus.
    - Subscribe and unsubscribe any method or function in the codebase to topics
      through @on and @off decorators.

    TODO: Wildcard topics, priority handlers, etc.

    """

    def __init__(self):
        """Initialize the message bus and its registries."""

        self._handlers: QiHandlerManager = QiHandlerManager()
        self._connections: QiConnectionManager = QiConnectionManager()
        self._messages: QiMessageManager = QiMessageManager()

    @classmethod
    async def shutdown(cls) -> None:
        """Close all connections, clear registries and drop singleton."""

        # Close sockets
        await asyncio.gather(
            [conn.socket.close() for conn in cls._instance._connections.by_id.values()],
            return_exceptions=True,
        )

        # Clear registries
        cls._instance._handlers.clear()
        cls._instance._connections.clear()
        cls._instance._messages.clear()

        # Drop singleton
        QiMessageBusSingletonMeta._instance = None

    @classmethod
    def reset(cls) -> None:
        """Fire-and-forget shutdown in tests."""
        asyncio.get_event_loop().create_task(cls.shutdown())

    async def connect(self, socket: WebSocket, source: QiConnectionSource) -> None:
        """Connect a WebSocket to the message bus."""

        await socket.accept()

        connection_id = str(uuid.uuid4())
        connection = QiConnection(
            connection_id=connection_id,
            socket=socket,
            source=source,
        )
        self._close_duplicate_connections(source)
        self._connections.register(connection)

    async def _close_duplicate_connections(self, source: QiConnectionSource) -> None:
        """Close any existing connections with the same session+window combination."""
        for conn in self._connections.get_by_source(source, source.type):
            pass

    def list_handlers(self) -> None:
        """List all registered handlers for debugging."""
        for topic, handlers in self._handlers.by_topic.items():
            log.debug(
                f"Topic: '{topic}' has {len(handlers)} registered handlers: '{[h.__name__ for h in handlers]}'"
            )

    def on(self, topic: str) -> Callable[[Handler], Handler]:
        """Subscribe a handler to a topic."""
        topic = topic.strip()

        def decorator(func: Handler) -> Handler:
            self._handlers.register(func, topic)
            log.debug(f"Registered handler: '{func.__name__}' on topic: '{topic}'")
            return func

        return decorator

    def off(self, topic: str, handler: Handler) -> None:
        """Unsubscribe a handler from a topic."""
        topic = topic.strip()

        if topic not in self._handlers.by_topic:
            log.warning(f"Unsubscribed handler from non-existent topic: '{topic}'")
            return

        self._handlers.unregister(handler, topic)

        log.debug(f"Handler '{handler.__name__}' unsubscribed from '{topic}'")
