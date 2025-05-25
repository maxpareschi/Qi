"""
core/bus.py
-----------

Async event bus + WebSocket connection manager for Qi.

• One singleton (`bus`) imported everywhere.
• Envelope schema matches the format we agreed on.
• Pydantic validation is **strict in dev**, minimal in prod (flag QI_DEV_MODE).
• Automatic heartbeat, reconnection buffering and validation-error echo.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable, Optional, TypeAlias
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.logging import get_logger

# --------------------------------------------------------------------------- #
#                               CONFIG / CONSTANTS                            #
# --------------------------------------------------------------------------- #

PING_INTERVAL = 20  # seconds between pings
MAX_IDLE = 60  # drop if no pong in N seconds
MAX_QUEUE = 256  # unsent messages kept per session

log = get_logger(__name__)
qi_dev_mode = os.getenv("QI_DEV_MODE", "0") == "1"

# --------------------------------------------------------------------------- #
#                               ENVELOPE MODEL                                #
# --------------------------------------------------------------------------- #


class QiEnvelope(BaseModel):
    """
    Canonical message wrapper. Addons & UI see only this structure.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_default=qi_dev_mode,
        validate_assignment=False,
        strict=qi_dev_mode,
    )

    message_id: UUID = Field(default_factory=uuid.uuid4)
    topic: str
    context: dict[str, Any] = {}
    sender: dict[str, Any]
    reply_to: Optional[UUID] = None
    payload: Any


# --------------------------------------------------------------------------- #
#                            SINGLETON META CLASS                             #
# --------------------------------------------------------------------------- #


class _Singleton(type):
    _inst: "QiEventBus|None" = None

    def __call__(cls, *a, **kw):
        if cls._inst is None:
            cls._inst = super().__call__(*a, **kw)
        return cls._inst


Handler: TypeAlias = Callable[[QiEnvelope, str], Awaitable | None]

# --------------------------------------------------------------------------- #
#                                 EVENT BUS                                   #
# --------------------------------------------------------------------------- #


class QiEventBus(metaclass=_Singleton):
    """
    Routes envelopes, keeps WS registry, handles reconnection & heartbeat.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, set[Handler]] = defaultdict(set)  # topic → {handlers}
        self._ws: dict[str, WebSocket] = {}  # session → socket
        self._outbox: dict[str, deque[QiEnvelope]] = {}  # session → deque
        self._seen: dict[str, float] = {}  # session → last pong
        self._lock = asyncio.Lock()
        self._janitor_task: asyncio.Task | None = None

    # ------------------------------------------------------------------ API #

    def list_handlers(self) -> None:
        """List all registered handlers."""
        for topic, handlers in self._handlers.items():
            log.info(f"Handlers for topic: '{topic}'")
            for handler in handlers:
                log.info(f"> {handler.__name__}")

    def on(self, topic: str) -> Callable[[Handler], Handler]:
        """Decorator to register a handler for a specific topic.
        @bus.on("plugin.query")
        """

        topic = topic.strip()

        def decorator(func: Handler) -> Handler:
            log.info(f"Registering handler: '{func.__name__}' for pattern: '{topic}'")
            self._handlers[topic].add(func)
            return func

        return decorator

    async def accept(self, ws: WebSocket, session: str) -> None:
        """Attach (or re-attach) a WebSocket connection to *session*."""

        await ws.accept()

        async with self._lock:
            self._ws[session] = ws
            self._seen[session] = time.time()
            self._outbox.setdefault(session, deque(maxlen=MAX_QUEUE))

        # spawn pumps
        asyncio.create_task(self._pump_in(session), name=f"pump-in[{session}]")
        asyncio.create_task(self._pump_out(session), name=f"pump-out[{session}]")

        # make sure the janitor is running once
        if self._janitor_task is None:
            self._janitor_task = asyncio.create_task(
                self._janitor(), name="bus-janitor"
            )

    async def emit(
        self,
        topic: str,
        payload: Any,
        *,
        context: dict[str, Any] | None = None,
        reply_to: UUID | None = None,
        target: str | None = None,
        session: str = "server",
    ) -> None:
        """Build an Envelope, deliver to local handlers, enqueue for remote sockets."""

        env = QiEnvelope(
            topic=topic,
            context=context or {},
            sender={"session_id": session},
            reply_to=reply_to,
            payload=payload,
        )

        await self._dispatch(env)  # local listeners first

        async with self._lock:
            if target:
                self._outbox.setdefault(target, deque(maxlen=MAX_QUEUE)).append(env)
            else:
                for q in self._outbox.values():
                    q.append(env)

    async def close(self, session: str) -> None:
        async with self._lock:
            self._ws.pop(session, None)
            self._seen.pop(session, None)

    # ------------------------------- INTERNAL ------------------------------ #

    async def _dispatch(self, env: QiEnvelope) -> None:
        for fn in list(self._handlers.get(env.topic, ())):
            await call_or_await(
                fn(env, env.sender.get("session_id", env.context.get("session_id", "")))
            )

    async def _pump_in(self, session: str) -> None:
        try:
            while True:
                # Check if session still exists before proceeding
                async with self._lock:
                    if session not in self._ws:
                        break
                    ws = self._ws[session]

                raw = await ws.receive_json()

                # heartbeat reply
                if raw == {"pong": True}:
                    async with self._lock:
                        if session in self._seen:
                            self._seen[session] = time.time()
                    continue

                # validate envelope (strict dev / relaxed prod)
                try:
                    env = QiEnvelope.model_validate(raw)
                except ValidationError as err:
                    await self._send_validation_error(session, raw, err)
                    continue

                await self._dispatch(env)

        except WebSocketDisconnect:
            await self.close(session)

    async def _pump_out(self, session: str) -> None:
        try:
            while True:
                # Check if session still exists before proceeding
                async with self._lock:
                    if session not in self._ws or session not in self._outbox:
                        break
                    ws = self._ws[session]
                    outbox = self._outbox[session]

                # send heartbeat if nothing else
                if not outbox:
                    await ws.send_json({"ping": True})
                else:
                    env = outbox.popleft()
                    await ws.send_json(env.model_dump(mode="json"))
                await asyncio.sleep(0)  # cooperative yield
        except Exception:
            await self.close(session)

    async def _janitor(self) -> None:
        while True:
            await asyncio.sleep(PING_INTERVAL)
            now = time.time()
            async with self._lock:
                for sess, last in list(self._seen.items()):
                    if now - last > MAX_IDLE:
                        try:
                            await self._ws[sess].close(code=4408)
                        except Exception:
                            pass
                        await self.close(sess)

    async def _send_validation_error(
        self, session: str, raw: Any, err: ValidationError
    ) -> None:
        await self.emit(
            topic="qi.error.validation",
            data={
                "message": "Envelope validation failed",
                "errors": err.errors(),
                "raw": raw,
            },
            target=session,
            session="server",
        )

    # -------------------- helper for AddonLoader hot-swap ------------------ #
    def unregister_module(self, mod_name: str) -> None:
        for topic, fns in list(self._handlers.items()):
            for fn in list(fns):
                if fn.__module__ == mod_name:
                    fns.discard(fn)
            if not fns:
                self._handlers.pop(topic, None)


# --------------------------------------------------------------------------- #
#                               PUBLIC SINGLETON                              #
# --------------------------------------------------------------------------- #

qi_bus = QiEventBus()

# --------------------------------------------------------------------------- #
#                                  UTILITIES                                  #
# --------------------------------------------------------------------------- #


async def call_or_await(res):
    if inspect.isawaitable(res):
        return await res
    return res
