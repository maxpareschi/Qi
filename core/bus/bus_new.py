"""
core/bus.py
-----------

Simple async event bus + WebSocket connection manager for Qi.

• One singleton (`bus`) imported everywhere.
• Event schema for structured messaging.
• Direct WebSocket handling without complex pump system.

Use direct class instantiation for consistency:
• bus = QiEventBus()  # Always returns the singleton instance

"""

import asyncio
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeAlias

from fastapi import WebSocket, WebSocketDisconnect

from core import logger
from core.bus.event import QiContext, QiEvent, QiSource, QiUser

# --------------------------------------------------------------------------- #
#                               CONFIG / CONSTANTS                            #
# --------------------------------------------------------------------------- #


log = logger.get_logger(__name__)
Handler: TypeAlias = Callable[[QiEvent], Awaitable | None]


# --------------------------------------------------------------------------- #
#                           CONNECTION TRACKING                               #
# --------------------------------------------------------------------------- #


@dataclass
class QiConnection:
    """WebSocket connection with metadata."""

    websocket: WebSocket
    session_id: str
    addon: str | None = None
    window_id: str | None = None


# --------------------------------------------------------------------------- #
#                            SINGLETON META CLASS                             #
# --------------------------------------------------------------------------- #


class QiEventBusSingleton(type):
    _inst: "QiEventBus|None" = None

    def __call__(cls, *a, **kw):
        if cls._inst is None:
            cls._inst = super().__call__(*a, **kw)
        return cls._inst

    def reset(cls):
        """Reset singleton for testing."""
        if cls._inst is not None:
            # Clean up existing connections before reset
            if hasattr(cls._inst, "_connections"):
                for conn in cls._inst._connections.values():
                    try:
                        asyncio.create_task(conn.websocket.close())
                    except Exception:
                        pass  # WebSocket might already be closed
                cls._inst._connections.clear()
        cls._inst = None


# --------------------------------------------------------------------------- #
#                                 EVENT BUS                                   #
# --------------------------------------------------------------------------- #


class QiEventBus(metaclass=QiEventBusSingleton):
    """Singleton event bus for inter-addon communication."""

    def __init__(self) -> None:
        # Handlers dict with topic -> set of handlers
        self._handlers: dict[str, set[Handler]] = defaultdict(set)

        # Connection dict with UUID -> QiConnection
        self._connections: dict[str, QiConnection] = {}

    # ------------------------------- API ----------------------------------- #

    def list_handlers(self) -> None:
        """List all registered handlers for debugging."""
        for topic, handlers in self._handlers.items():
            log.debug(
                f"Topic: '{topic}' has {len(handlers)} registered handlers: '{[h.__name__ for h in handlers]}'"
            )

    def on(self, topic: str) -> Callable[[Handler], Handler]:
        """Register a handler for a topic."""
        topic = topic.strip()

        def decorator(func: Handler) -> Handler:
            self._handlers[topic].add(func)
            log.debug(f"Registered handler: '{func.__name__}' on topic: '{topic}'")
            return func

        return decorator

    async def connect(
        self, ws: WebSocket, session_id: str, window_id: str = None
    ) -> None:
        """Register a WebSocket connection."""
        await ws.accept()

        # Create connection object
        connection = QiConnection(
            websocket=ws,
            session_id=session_id,
            window_id=window_id,
        )

        # Close any duplicate connections
        await self._close_duplicate_connections(session_id, window_id)

        # Store connection with unique UUID key
        connection_id = str(uuid.uuid4())
        self._connections[connection_id] = connection

        log.debug(
            f"WebSocket connected: session={session_id[:8]}..., window={window_id or 'none'}"
        )

        try:
            # Use async iteration - FastAPI handles connection state automatically
            async for message in ws.iter_text():
                try:
                    event_data = json.loads(message)
                    event = QiEvent.model_validate(event_data)

                    # Auto-detect addon from first message if not known
                    if connection.addon is None and event.source and event.source.addon:
                        connection.addon = event.source.addon
                        log.info(
                            f"Auto-detected addon '{event.source.addon}' for session {session_id[:8]}..."
                        )

                    await self._dispatch(event, from_client=True)

                except json.JSONDecodeError as e:
                    log.warning(f"Invalid JSON received from {session_id[:8]}...: {e}")
                    # Send error response to client if still connected
                    if self._is_connected(ws):
                        try:
                            await ws.send_text(
                                json.dumps(
                                    {"error": "Invalid JSON format", "message": str(e)}
                                )
                            )
                        except Exception as send_error:
                            log.warning(
                                f"Failed to send error response to {session_id[:8]}...: {send_error}"
                            )
                except Exception as e:
                    log.error(f"Error processing message from {session_id[:8]}...: {e}")

        except WebSocketDisconnect:
            pass  # Normal disconnection
        except Exception as e:
            log.error(f"Connection error for {session_id[:8]}...: {e}")
        finally:
            # Always clean up connection when exiting
            if connection_id in self._connections:
                del self._connections[connection_id]
            log.info(f"WebSocket disconnected: session={session_id[:8]}...")

    async def emit(
        self,
        topic: str,
        *,
        payload: dict[str, Any] | None = None,
        context: dict[str, Any] | QiContext | None = None,
        source: dict[str, Any] | QiSource | None = None,
        user: dict[str, Any] | QiUser | None = None,
        reply_to: str | None = None,
    ) -> None:
        """Emit a message to the bus with intelligent auto-filling."""

        # Convert context to QiContext if needed
        if isinstance(context, dict):
            context = QiContext.model_validate(context)
        elif context is None:
            context = QiContext.from_env()  # Auto-fill from environment

        # Convert source to QiSource if needed
        if isinstance(source, dict):
            source = QiSource.model_validate(source)
        # Note: source is often None for server-originated messages

        # Convert user to QiUser if needed
        if isinstance(user, dict):
            user = QiUser.model_validate(user)

        event = QiEvent(
            topic=topic,
            payload=payload or {},
            context=context,
            source=source,
            user=user,
            reply_to=reply_to,
        )

        await self._dispatch(event, from_client=False)

    # ------------------------------- INTERNAL ------------------------------ #

    def _is_connected(self, ws: WebSocket) -> bool:
        """Check if WebSocket is still connected."""
        try:
            return ws.client_state.name == "CONNECTED"
        except Exception:
            return False

    def _cleanup_connection(self, connection_id: str) -> None:
        """Clean up a disconnected connection by ID."""
        if connection_id in self._connections:
            del self._connections[connection_id]

    async def _close_duplicate_connections(
        self, session_id: str, window_id: str
    ) -> None:
        """Close any existing connections with the same session+window combination."""
        duplicates_to_remove = []
        for conn_id, existing_conn in self._connections.items():
            if (
                existing_conn.session_id == session_id
                and existing_conn.window_id == window_id
            ):
                log.warning(
                    f"Closing duplicate: session={session_id[:8]}, window={window_id}"
                )
                try:
                    await existing_conn.websocket.close()
                except Exception as e:
                    log.warning(f"Error closing existing connection: {e}")
                duplicates_to_remove.append(conn_id)

        # Clean up duplicates after the loop
        for conn_id in duplicates_to_remove:
            del self._connections[conn_id]

    async def _dispatch(
        self,
        event: QiEvent,
        from_client: bool = False,
    ) -> None:
        """Dispatch message to handlers and route as needed."""

        # Always call local handlers first
        if event.topic in self._handlers:
            for handler in self._handlers[event.topic]:
                await self._call_handler(handler, event)

        # Route replies to original sender
        if event.reply_to:
            await self._route_reply(event)
        # Otherwise broadcast normally (unless it's from a client)
        elif not from_client:
            await self._broadcast(event)

    async def _route_reply(self, event: QiEvent) -> None:
        """Route reply message to original sender."""
        if not event.reply_to:
            log.warning("Reply message has no reply_to field")
            return

        if event.source and event.source.session_id:
            target_session_id = event.source.session_id
            target_window_id = event.source.window_id

            # Find matching connections
            target_connections = [
                conn
                for conn in self._connections.values()
                if conn.session_id == target_session_id
                and (target_window_id is None or target_window_id == conn.window_id)
            ]

            # Send to found connections
            sent_count = 0
            for connection in target_connections:
                try:
                    if self._is_connected(connection.websocket):
                        await connection.websocket.send_text(event.model_dump_json())
                        sent_count += 1
                except Exception as e:
                    log.warning(
                        f"Failed to send reply to session {connection.session_id}: {e}"
                    )

            log.debug(
                f"Routed reply {event.topic} → {sent_count}/{len(target_connections)} connections"
            )
        else:
            log.warning(f"Reply message has no source for routing: {event.reply_to}")

    async def _broadcast(self, event: QiEvent) -> None:
        """Broadcast message to all connected clients."""
        if not self._connections:
            log.debug(f"No connections for broadcast: {event.topic}")
            return

        message = event.model_dump_json()
        sent_count = 0

        for connection in self._connections.values():
            try:
                if self._is_connected(connection.websocket):
                    await connection.websocket.send_text(message)
                    sent_count += 1
            except Exception as e:
                log.warning(
                    f"Failed to broadcast to session {connection.session_id}: {e}"
                )

        log.debug(
            f"Broadcasted {event.topic} to {sent_count}/{len(self._connections)} connections"
        )

    async def _call_handler(self, handler: Handler, event: QiEvent) -> None:
        """Call a message handler safely."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                # Run sync handler in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, event)
        except Exception as e:
            log.error(f"Handler error for {event.topic}: {e}", exc_info=True)

    # ------------------------------- UTILITIES ----------------------------- #

    def get_connections_by_session(self, session_id: str) -> list[QiConnection]:
        """Get all connections for a session."""
        return [
            conn for conn in self._connections.values() if conn.session_id == session_id
        ]

    def get_connections_by_addon(self, addon: str) -> list[QiConnection]:
        """Get all connections for an addon."""
        return [conn for conn in self._connections.values() if conn.addon == addon]

    def get_connections_by_window(
        self, session_id: str, window_id: str
    ) -> list[QiConnection]:
        """Get connections for a specific window in a session."""
        return [
            conn
            for conn in self._connections.values()
            if conn.session_id == session_id and conn.window_id == window_id
        ]

    def get_connection_info(self) -> dict[str, Any]:
        """Get debug info about all connections."""
        # Group connections by session for display
        sessions = defaultdict(list)
        for conn in self._connections.values():
            sessions[conn.session_id].append(
                {
                    "addon": conn.addon,
                    "window_id": conn.window_id,
                }
            )

        return {
            "total_connections": len(self._connections),
            "total_sessions": len(sessions),
            "sessions": dict(sessions),
        }
