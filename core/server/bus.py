"""
core/bus.py
-----------

Simple async event bus + WebSocket connection manager for Qi.

• One singleton (`bus`) imported everywhere.
• Envelope schema for structured messaging.
• Direct WebSocket handling without complex pump system.
"""

import asyncio
import json
import os
import time
import uuid
from collections import defaultdict
from typing import Any, Awaitable, Callable, Optional, TypeAlias

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

from core import logger

# --------------------------------------------------------------------------- #
#                               CONFIG / CONSTANTS                            #
# --------------------------------------------------------------------------- #

log = logger.get_logger(__name__)
qi_dev_mode = os.getenv("QI_DEV_MODE", "0") == "1"

# --------------------------------------------------------------------------- #
#                               ENVELOPE MODEL                                #
# --------------------------------------------------------------------------- #


class QiContext(BaseModel):
    """Business context for pipeline/project decisions."""

    project: Optional[str] = None
    entity: Optional[str] = None
    task: Optional[str] = None
    # Extra context can be added as needed

    @classmethod
    def from_env(cls) -> "QiContext":
        return cls(
            project=os.getenv("QI_PROJECT", None),
            entity=os.getenv("QI_ENTITY", None),
            task=os.getenv("QI_TASK", None),
        )


class QiUser(BaseModel):
    """User information for auth and user-specific routing."""

    id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    # Future: auth tokens, permissions, etc.


class QiSource(BaseModel):
    """Source information for message routing."""

    addon: str
    session_id: str
    window_id: Optional[str] = None
    user: Optional[QiUser] = None


class QiEnvelope(BaseModel):
    """Canonical message wrapper with separated concerns."""

    model_config = ConfigDict(
        extra="forbid",
        validate_default=qi_dev_mode,
        validate_assignment=False,
        strict=qi_dev_mode,
    )

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = Field(default="")
    payload: dict[str, Any] = Field(default_factory=dict)
    context: Optional[QiContext] = Field(default=None)
    source: Optional[QiSource] = Field(default=None)
    user: Optional[QiUser] = Field(default=None)
    reply_to: Optional[str] = Field(default=None)
    timestamp: float = Field(default_factory=time.time)


# --------------------------------------------------------------------------- #
#                            SINGLETON META CLASS                             #
# --------------------------------------------------------------------------- #


class _Singleton(type):
    _inst: "QiEventBus|None" = None

    def __call__(cls, *a, **kw):
        if cls._inst is None:
            cls._inst = super().__call__(*a, **kw)
        return cls._inst

    def reset(cls):
        """Reset singleton for testing."""
        cls._inst = None


Handler: TypeAlias = Callable[[QiEnvelope], Awaitable | None]

# --------------------------------------------------------------------------- #
#                                 EVENT BUS                                   #
# --------------------------------------------------------------------------- #


class QiEventBus(metaclass=_Singleton):
    """Singleton event bus for inter-addon communication."""

    def __init__(self) -> None:
        self._handlers: dict[str, set[Handler]] = defaultdict(set)
        self._sessions: dict[str, WebSocket] = {}
        # Track windows within sessions: {session_id: {window_id: WebSocket}}
        self._windows: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        self._message_registry: dict[str, QiEnvelope] = {}
        self._reply_routes: dict[str, tuple[str, Optional[str]]] = {}
        self._connections: dict[str, dict[str, WebSocket]] = {}
        self._session_to_addon: dict[str, str] = {}

    # ------------------------------------------------------------------ API #

    def list_handlers(self) -> None:
        """List all registered handlers for debugging."""
        for topic, handlers in self._handlers.items():
            log.info(f"Topic '{topic}': {len(handlers)} handlers")

    def on(self, topic: str) -> Callable[[Handler], Handler]:
        """Register a handler for a topic."""
        topic = topic.strip()

        def decorator(func: Handler) -> Handler:
            log.debug(f"📝 Handler '{func.__name__}' → {topic}")
            self._handlers[topic].add(func)
            return func

        return decorator

    async def connect(
        self, ws: WebSocket, session_id: str, window_id: str = None
    ) -> None:
        """Register a WebSocket connection."""
        await ws.accept()

        # Initialize session storage if needed
        if session_id not in self._connections:
            self._connections[session_id] = {}

        # Store connection with window_id as key
        window_key = window_id or "default"
        self._connections[session_id][window_key] = ws

        # Auto-detect addon from connection (if not already known)
        if session_id not in self._session_to_addon:
            # Try to detect addon from WebSocket headers or URL
            # For now, we'll wait for the first message to determine addon
            pass

        log.info(
            f"WebSocket connected: session={session_id[:8]}..., window={window_key[:8] if window_key != 'default' else 'default'}"
        )

        try:
            while True:
                data = await ws.receive_text()
                envelope_data = json.loads(data) if isinstance(data, str) else data
                envelope = QiEnvelope.model_validate(envelope_data)

                # Auto-detect addon from first message if not known
                if session_id not in self._session_to_addon and envelope.source:
                    self._session_to_addon[session_id] = envelope.source.addon
                    log.info(
                        f"Auto-detected addon '{envelope.source.addon}' for session {session_id[:8]}..."
                    )

                # Store reply route for this message
                if envelope.source:
                    self._reply_routes[str(envelope.message_id)] = (
                        session_id,
                        window_id,
                    )

                await self._dispatch(envelope, from_client=True)

        except WebSocketDisconnect:
            # Clean up connection
            if (
                session_id in self._connections
                and window_key in self._connections[session_id]
            ):
                del self._connections[session_id][window_key]
                if not self._connections[
                    session_id
                ]:  # No more windows for this session
                    del self._connections[session_id]
                    if session_id in self._session_to_addon:
                        del self._session_to_addon[session_id]

            log.info(
                f"WebSocket disconnected: session={session_id[:8]}..., window={window_key[:8] if window_key != 'default' else 'default'}"
            )

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

        envelope = QiEnvelope(
            topic=topic,
            payload=payload or {},
            context=context,
            source=source,
            user=user,
            reply_to=reply_to,
        )

        await self._dispatch(envelope, from_client=False)

    # ------------------------------- INTERNAL ------------------------------ #

    async def _dispatch(self, envelope: QiEnvelope, from_client: bool = False) -> None:
        """Dispatch message to handlers and route as needed."""

        # Always call local handlers first
        if envelope.topic in self._handlers:
            for handler in self._handlers[envelope.topic]:
                await self._call_handler(handler, envelope)

        # Route replies to original sender
        if envelope.reply_to:
            await self._route_reply(envelope)
        # Otherwise broadcast normally (unless it's from a client)
        elif not from_client:
            await self._broadcast(envelope)

    async def _route_reply(self, envelope: QiEnvelope) -> None:
        """Route reply message to original sender."""
        reply_to_str = str(envelope.reply_to)

        if reply_to_str in self._reply_routes:
            target_session_id, target_window_id = self._reply_routes[reply_to_str]

            # Send to specific session/window
            if target_session_id in self._connections:
                session_connections = self._connections[target_session_id]

                if target_window_id and target_window_id in session_connections:
                    # Send to specific window
                    target_connections = {
                        target_session_id: {
                            target_window_id: session_connections[target_window_id]
                        }
                    }
                    await self._send_message(envelope, target_connections)
                else:
                    # Send to all windows in session
                    target_connections = {target_session_id: session_connections}
                    await self._send_message(envelope, target_connections)

                log.debug(
                    f"Routed reply {envelope.topic} → session {target_session_id[:8]}..."
                )
            else:
                log.warning(f"Reply target session {target_session_id} not connected")

            # Clean up reply route after use
            del self._reply_routes[reply_to_str]
        else:
            log.warning(f"No reply route found for message {reply_to_str}")

    async def _send_message(
        self, envelope: QiEnvelope, connections: dict = None
    ) -> None:
        """Send message to specified connections or all connections."""
        message = envelope.model_dump_json()
        target_connections = connections or self._connections

        disconnected = []

        for session_id, session_connections in target_connections.items():
            if isinstance(session_connections, dict):
                # Multiple windows in session
                for window_id, ws in session_connections.items():
                    try:
                        await ws.send_text(message)
                    except Exception as e:
                        log.warning(f"Failed to send to {session_id}:{window_id}: {e}")
                        disconnected.append((session_id, window_id))
            else:
                # Single WebSocket connection (legacy)
                try:
                    await session_connections.send_text(message)
                except Exception as e:
                    log.warning(f"Failed to send to {session_id}: {e}")
                    disconnected.append((session_id, None))

        # Clean up disconnected connections
        for session_id, window_id in disconnected:
            if session_id in self._connections:
                if window_id:
                    if window_id in self._connections[session_id]:
                        del self._connections[session_id][window_id]
                        if not self._connections[session_id]:
                            del self._connections[session_id]
                            if session_id in self._session_to_addon:
                                del self._session_to_addon[session_id]
                else:
                    del self._connections[session_id]
                    if session_id in self._session_to_addon:
                        del self._session_to_addon[session_id]

    async def _broadcast(self, envelope: QiEnvelope) -> None:
        """Broadcast message to all connected clients."""
        if not self._connections:
            log.debug(f"No connections for broadcast: {envelope.topic}")
            return

        await self._send_message(envelope)
        total_connections = sum(len(conns) for conns in self._connections.values())
        log.debug(f"Broadcasted {envelope.topic} to {total_connections} connections")

    async def _call_handler(self, handler: Handler, envelope: QiEnvelope) -> None:
        """Call a message handler safely."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(envelope)
            else:
                # Run sync handler in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, envelope)
        except Exception as e:
            log.error(f"Handler error for {envelope.topic}: {e}", exc_info=True)


# --------------------------------------------------------------------------- #
#                               PUBLIC SINGLETON                              #
# --------------------------------------------------------------------------- #

qi_bus = QiEventBus()

# ============================================================================
# Helper functions
# ============================================================================


def get_session_id_from_source(envelope: QiEnvelope) -> str:
    """Helper to extract session_id from envelope source."""
    return envelope.source.session_id if envelope.source else "unknown"


def get_addon_from_source(envelope: QiEnvelope) -> str:
    """Helper to extract addon from envelope source."""
    return envelope.source.addon if envelope.source else "unknown"


def get_window_id_from_source(envelope: QiEnvelope) -> Optional[str]:
    """Helper to extract window_id from envelope source."""
    return envelope.source.window_id if envelope.source else None
