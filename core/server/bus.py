"""
core/bus.py
-----------

Simple async event bus + WebSocket connection manager for Qi.

• One singleton (`bus`) imported everywhere.
• Envelope schema for structured messaging.
• Direct WebSocket handling without complex pump system.
"""

from __future__ import annotations

import inspect
import os
import time
import uuid
from collections import defaultdict
from typing import Any, Awaitable, Callable, Optional, TypeAlias
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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
    project: Optional[str] = None
    entity: Optional[str] = None
    task: Optional[str] = None
    session: Optional[str] = None
    window_uuid: Optional[str] = None  # Identifies specific window within session

    @field_validator("window_uuid", mode="before")
    @classmethod
    def validate_window_uuid(cls, v):
        """Handle window_uuid validation - convert invalid values to None."""
        if v is None:
            return None
        if v == {} or v == "" or v == []:
            return None
        if isinstance(v, dict):
            log.warning(f"window_uuid received as dict: {v}, converting to None")
            return None
        if not isinstance(v, str):
            log.warning(f"window_uuid received as {type(v)}: {v}, converting to None")
            return None
        return v

    @classmethod
    def from_env(cls) -> "QiContext":
        return cls(
            project=os.getenv("QI_PROJECT"),
            entity=os.getenv("QI_ENTITY"),
            task=os.getenv("QI_TASK"),
            session=os.getenv("QI_SESSION"),
            window_uuid=os.getenv("QI_WINDOW_UUID"),  # Usually set by client
        )


class QiEnvelope(BaseModel):
    """Canonical message wrapper."""

    model_config = ConfigDict(
        extra="forbid",
        validate_default=qi_dev_mode,
        validate_assignment=False,
        strict=qi_dev_mode,
    )

    message_id: UUID = Field(default_factory=uuid.uuid4)
    topic: str = Field(default="")
    payload: dict[str, Any] = Field(default_factory=dict)
    context: Optional[QiContext] = Field(default=None)
    reply_to: Optional[UUID] = Field(default=None)
    timestamp: float = Field(default_factory=time.time)

    @field_validator("message_id", "reply_to", mode="before")
    @classmethod
    def validate_uuid_fields(cls, v):
        """Convert string UUIDs to UUID objects for JavaScript compatibility."""
        if v is None:
            return v
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                raise ValueError(f"Invalid UUID string: {v}")
        return v


# --------------------------------------------------------------------------- #
#                            SINGLETON META CLASS                             #
# --------------------------------------------------------------------------- #


class _Singleton(type):
    _inst: "QiEventBus|None" = None

    def __call__(cls, *a, **kw):
        if cls._inst is None:
            cls._inst = super().__call__(*a, **kw)
        return cls._inst


Handler: TypeAlias = Callable[[QiEnvelope], Awaitable | None]

# --------------------------------------------------------------------------- #
#                                 EVENT BUS                                   #
# --------------------------------------------------------------------------- #


class QiEventBus(metaclass=_Singleton):
    """Simple event bus for routing envelopes."""

    def __init__(self) -> None:
        self._handlers: dict[str, set[Handler]] = defaultdict(set)
        self._sessions: dict[str, WebSocket] = {}
        # Track windows within sessions: {session: {window_uuid: WebSocket}}
        self._windows: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        self._message_registry: dict[UUID, QiEnvelope] = {}

    # ------------------------------------------------------------------ API #

    def list_handlers(self) -> None:
        """List all registered handlers."""
        for topic, handlers in self._handlers.items():
            log.debug(
                f"Handlers for topic: '{topic}' : {[handler.__name__ for handler in handlers]}"
            )

    def on(self, topic: str) -> Callable[[Handler], Handler]:
        """Register a handler for a topic."""
        topic = topic.strip()

        def decorator(func: Handler) -> Handler:
            log.debug(f"📝 Handler '{func.__name__}' → {topic}")
            self._handlers[topic].add(func)
            return func

        return decorator

    async def connect(
        self, ws: WebSocket, session: str, window_uuid: str = None
    ) -> None:
        """Connect a WebSocket session with optional window tracking."""
        if window_uuid:
            log.info(f"🔌 Connected window {window_uuid[:8]}... in session {session}")
        else:
            log.info(f"🔌 Connected session {session}")

        await ws.accept()
        self._sessions[session] = ws

        # Track window if window_uuid provided
        if window_uuid:
            self._windows[session][window_uuid] = ws

        # Handle incoming messages
        try:
            while True:
                try:
                    data = await ws.receive_json()
                    if data == {"ping": True}:
                        await ws.send_json({"pong": True})
                        continue

                    # Validate and dispatch message
                    try:
                        envelope = QiEnvelope.model_validate(data)
                        self._message_registry[envelope.message_id] = envelope
                        await self._dispatch(envelope, from_client=True)
                    except ValidationError as e:
                        log.error(f"Invalid message from {session}: {e}")
                        await ws.send_json(
                            {"error": "validation_error", "details": str(e)}
                        )

                except WebSocketDisconnect:
                    break
                except Exception as e:
                    log.error(f"Error handling message from {session}: {e}")
                    break

        finally:
            if window_uuid:
                log.info(f"🔌 Disconnected window {window_uuid[:8]}...")
            else:
                log.info(f"🔌 Disconnected session {session}")

            self._sessions.pop(session, None)

            # Remove window tracking
            if window_uuid and session in self._windows:
                self._windows[session].pop(window_uuid, None)
                # Clean up empty session entries
                if not self._windows[session]:
                    del self._windows[session]

    async def emit(
        self,
        topic: str,
        *,
        payload: dict[str, Any] | None = None,
        context: dict[str, Any] | QiContext | None = None,
        reply_to: UUID | str | None = None,
    ) -> None:
        """Send a message."""

        # Handle context
        if isinstance(context, dict):
            ctx = QiContext(**context)
        elif context is None:
            ctx = QiContext()
        else:
            ctx = context

        # Handle reply_to
        reply_uuid = None
        if reply_to is not None:
            if isinstance(reply_to, str):
                try:
                    reply_uuid = UUID(reply_to)
                except ValueError:
                    log.warning(f"Invalid UUID for reply_to: {reply_to}")
            else:
                reply_uuid = reply_to

        # Auto-inherit context for replies
        if reply_uuid and context is None:
            original_msg = self._message_registry.get(reply_uuid)
            if original_msg and original_msg.context:
                ctx = QiContext(
                    project=original_msg.context.project,
                    entity=original_msg.context.entity,
                    task=original_msg.context.task,
                    session=original_msg.context.session,
                    window_uuid=original_msg.context.window_uuid,
                )

        envelope = QiEnvelope(
            topic=topic,
            context=ctx,
            reply_to=reply_uuid,
            payload=payload or {},
        )

        self._message_registry[envelope.message_id] = envelope
        await self._dispatch(envelope, from_client=False)

    # ------------------------------- INTERNAL ------------------------------ #

    async def _dispatch(self, envelope: QiEnvelope, from_client: bool = False) -> None:
        """Dispatch message to handlers and/or WebSocket sessions."""

        # Dispatch to local handlers
        handlers = self._handlers.get(envelope.topic, set())
        if handlers:
            log.debug(f"🚀 Dispatching {envelope.topic} to {len(handlers)} handlers")

        for handler in handlers:
            try:
                await self._call_handler(handler, envelope)
            except Exception as e:
                log.error(f"Handler {handler.__name__} failed: {e}")

        # Only route to clients if this is a server-originated message or a reply
        if not from_client:
            # Route replies to original sender
            if envelope.reply_to:
                await self._route_reply(envelope)
            else:
                # Send to specific window or broadcast
                await self._send_message(envelope)

    async def _route_reply(self, envelope: QiEnvelope) -> None:
        """Route reply to original sender with window-specific targeting."""
        original_msg = self._message_registry.get(envelope.reply_to)
        if (
            not original_msg
            or not original_msg.context
            or not original_msg.context.session
        ):
            log.warning(f"Cannot route reply for {envelope.reply_to}")
            return

        target_session = original_msg.context.session
        target_window_uuid = original_msg.context.window_uuid

        # Try window-specific routing first
        if target_window_uuid and target_session in self._windows:
            target_ws = self._windows[target_session].get(target_window_uuid)
            if target_ws:
                try:
                    await target_ws.send_json(envelope.model_dump(mode="json"))
                    log.debug(f"✅ Reply → {target_window_uuid[:8]}...")
                    return
                except Exception as e:
                    log.error(
                        f"Failed to send reply to {target_session}/{target_window_uuid}: {e}"
                    )
                    # Remove dead window connection
                    self._windows[target_session].pop(target_window_uuid, None)

        # Fallback to session-level routing
        if target_session in self._sessions:
            try:
                await self._sessions[target_session].send_json(
                    envelope.model_dump(mode="json")
                )
                log.debug(f"✅ Reply → session {target_session}")
            except Exception as e:
                log.error(f"Failed to send reply to {target_session}: {e}")
                # Remove dead session
                self._sessions.pop(target_session, None)

    async def _send_message(self, envelope: QiEnvelope) -> None:
        """Send message with window-specific targeting or broadcast."""
        # Check if message has window targeting
        if (
            envelope.context
            and envelope.context.window_uuid
            and envelope.context.session
        ):
            target_session = envelope.context.session
            target_window_uuid = envelope.context.window_uuid

            # Send to specific window
            if target_session in self._windows:
                target_ws = self._windows[target_session].get(target_window_uuid)
                if target_ws:
                    try:
                        await target_ws.send_json(envelope.model_dump(mode="json"))
                        log.debug(f"📤 Message → {target_window_uuid[:8]}...")
                        return
                    except Exception as e:
                        log.error(
                            f"Failed to send to {target_session}/{target_window_uuid}: {e}"
                        )
                        # Remove dead window connection
                        self._windows[target_session].pop(target_window_uuid, None)

            log.warning(
                f"Window {target_window_uuid} in session {target_session} not found, broadcasting instead"
            )

        # Broadcast to all sessions if no window targeting or window not found
        await self._broadcast(envelope)

    async def _broadcast(self, envelope: QiEnvelope) -> None:
        """Broadcast message to all connected sessions."""
        if not self._sessions:
            return

        data = envelope.model_dump(mode="json")
        dead_sessions = []

        for session, ws in self._sessions.items():
            try:
                await ws.send_json(data)
                log.debug(f"📤 Broadcast → {session}")
            except Exception as e:
                log.error(f"Failed to broadcast to {session}: {e}")
                dead_sessions.append(session)

        # Clean up dead sessions
        for session in dead_sessions:
            self._sessions.pop(session, None)
            self._windows.pop(session, None)

    async def _call_handler(self, handler: Handler, envelope: QiEnvelope) -> None:
        """Call a handler function."""
        result = handler(envelope)
        if inspect.isawaitable(result):
            await result


# --------------------------------------------------------------------------- #
#                               PUBLIC SINGLETON                              #
# --------------------------------------------------------------------------- #

qi_bus = QiEventBus()
