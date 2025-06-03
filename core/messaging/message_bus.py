# core/messaging/message_bus.py

import asyncio
import inspect
from typing import Any, List
from uuid import uuid4

from fastapi import WebSocket

from core.bases.models import QiContext, QiMessage, QiMessageType, QiSession
from core.config import qi_config
from core.constants import HUB_ID
from core.logger import get_logger
from core.messaging.connection_manager import QiConnectionManager
from core.messaging.handler_registry import QiHandlerRegistry

log = get_logger(__name__)


class QiMessageBus:
    """
    Routes QiMessage between connected sessions over WebSocket.

    ● Maintains a QiConnectionManager to track live sockets/sessions
    ● Maintains a QiHandlerRegistry to track topic → handler functions per session
    ● Tracks in‐flight REQUEST futures, so that a handler's return value can be
      auto‐wrapped as a REPLY back to the original requester.
    """

    def __init__(self) -> None:
        self._connection_manager: QiConnectionManager = QiConnectionManager()
        self._handler_registry: QiHandlerRegistry = QiHandlerRegistry()

        self._reply_timeout = qi_config.reply_timeout
        self._max_pending = qi_config.max_pending_requests_per_session

        # message_id → Future awaiting a reply payload
        self._pending_request_futures: dict[str, asyncio.Future[Any]] = {}
        # session_id → set of pending message_ids that originated from that session
        self._session_to_pending: dict[str, set[str]] = {}

        self._lock = asyncio.Lock()

    ########### SESSION LIFECYCLE ###########

    async def register(self, *, socket: WebSocket, session: QiSession) -> None:
        """
        Called right after a client WebSocket handshake.
        Registers the socket+session in the ConnectionManager.

        Args:
            socket:  the accepted WebSocket instance
            session: a QiSession object (with fields id, logical_id, parent_logical_id, tags)
        """
        await self._connection_manager.register(socket=socket, session=session)
        # (Optional) lifecycle hooks could go here

    async def unregister(self, *, session_id: str) -> None:
        """
        Called when a WebSocket disconnects or is torn down unexpectedly.
        1) Cancels any pending request futures from that session
        2) Drops all handlers registered by that session
        3) Unregisters the session (and its children) from ConnectionManager

        Args:
            session_id: the low‐level ID that was used in QiSession.id
        """
        # 1) Cancel in‐flight request futures for this session
        async with self._lock:
            pending_ids = self._session_to_pending.pop(session_id, set())
            for message_id in pending_ids:
                future = self._pending_request_futures.pop(message_id, None)
                if future and not future.done():
                    future.set_exception(ConnectionAbortedError("Session disconnected"))

        # 2) Drop all handlers for this session
        await self._handler_registry.drop_session(session_id=session_id)

        # 3) Unregister from ConnectionManager (this also tears down children)
        await self._connection_manager.unregister(session_id=session_id)

        # (Optional) lifecycle hooks could go here

    ########### HANDLER SUBSCRIPTION API ###########

    def on(self, topic: str, *, session_id: str = HUB_ID):
        """
        Decorator to register a handler function for a given topic under session_id.

        Example usage:

            @hub.on("addon.reload", session_id="my-addon-session")
            async def handle_reload(message: QiMessage):
                ...

        Returns:
            A decorator that schedules an asyncio task to register the function.
        """

        def decorator(function: Any) -> Any:
            # Schedule asynchronous registration (fire‐and‐forget)
            asyncio.create_task(
                self._handler_registry.register(
                    handler_fn=function, topic=topic, session_id=session_id
                )
            )
            return function

        return decorator

    ########### PUBLISH VS REQUEST ###########

    async def publish(self, *, message: QiMessage) -> None:
        """
        Fire‐and‐forget an EVENT or REPLY.
        If message.type == REPLY and message.reply_to is set, attempt to resolve
        the matching future immediately and do NOT fan out to handlers.

        Otherwise, route to handlers/bubble/broadcast.

        Args:
            message: a QiMessage instance
        """
        # 1) If this is a REPLY that matches a pending request, resolve and return
        if message.type is QiMessageType.REPLY and message.reply_to:
            async with self._lock:
                future = self._pending_request_futures.pop(message.reply_to, None)
                if future:
                    # Remove this message_id from the originating session's set
                    for session_id, pending_ids in self._session_to_pending.items():
                        if message.reply_to in pending_ids:
                            pending_ids.remove(message.reply_to)
                            break

            if future and not future.done():
                future.set_result(message.payload)
            return

        # 2) Otherwise, it's either EVENT or REQUEST
        await self._dispatch_and_maybe_reply(message=message)

    async def request(
        self,
        *,
        topic: str,
        payload: dict[str, Any],
        context: dict[str, Any] | None = None,
        timeout: float | None = None,
        target: List[str] | None = None,
        parent_logical_id: str | None = None,
        session_id: str = HUB_ID,
    ) -> Any:
        """
        Send a REQUEST‐type QiMessage, await exactly one REPLY, then return its payload.

        Args:
            topic:             the topic to which handlers are subscribed
            payload:           a dict of data to send
            context:           optional context info
            timeout:           seconds to wait before raising asyncio.TimeoutError
            target:            list of target logical_ids (if omitted, it's a broadcast)
            parent_logical_id: optional parent logical_id for "bubble" logic
            parent_logical_id: optional parent logical_id for "bubble" logic
            session_id:        this session's logical ID

        Returns:
            The payload returned by the first handler that produces a non‐None result.

        Raises:
            asyncio.TimeoutError   if no REPLY arrives within <timeout>
            RuntimeError          if the session already has max_pending requests
        """
        if timeout is None:
            timeout = self._reply_timeout

        # 1) Construct the QiMessage
        message_id = str(uuid4())
        qi_session = QiSession(
            id=session_id,
            logical_id=session_id,
            parent_logical_id=parent_logical_id,
            tags=[],
        )
        message = QiMessage(
            message_id=message_id,
            topic=topic,
            type=QiMessageType.REQUEST,
            sender=qi_session,
            target=target or [],
            reply_to=None,
            context=QiContext(**context) if context else None,
            payload=payload,
            bubble=False,
        )

        # 2) Create and store a Future for the expected reply
        reply_future = asyncio.get_running_loop().create_future()
        async with self._lock:
            pending_set = self._session_to_pending.setdefault(session_id, set())
            if len(pending_set) >= self._max_pending:
                raise RuntimeError("Too many concurrent requests for this session")
            self._pending_request_futures[message_id] = reply_future
            pending_set.add(message_id)

        # 3) Publish the REQUEST (fire‐and‐forget)
        await self.publish(message=message)

        # 4) Await the reply or timeout
        try:
            result = await asyncio.wait_for(reply_future, timeout)
            return result
        finally:
            # Cleanup if timed out or canceled
            async with self._lock:
                self._pending_request_futures.pop(message_id, None)
                self._session_to_pending.get(session_id, set()).discard(message_id)

    ########### INTERNAL DISPATCH & REPLY LOGIC ###########

    async def _dispatch_and_maybe_reply(self, *, message: QiMessage) -> None:
        """
        Core logic for:
          • EVENT messages → simply fan out to matching sockets
          • REQUEST messages → invoke handlers; if any returns non‐None, auto‐send REPLY
          • REPLY messages (already handled in publish)

        Args:
            message: a QiMessage (type EVENT or REQUEST)
        """
        # 1) Snapshot handler functions for this topic + session
        handler_functions = await self._handler_registry.get_handlers(
            topic=message.topic, session_id=message.sender.logical_id
        )

        # 2a) If no handlers found, just fan‐out the original message
        if not handler_functions:
            await self._fan_out(message=message)
            return

        # 2b) If this is a REQUEST, run handlers in order, take the first non‐None
        if message.type is QiMessageType.REQUEST:
            reply_payload: Any = None
            for function in handler_functions:
                try:
                    if inspect.iscoroutinefunction(function):
                        result = await function(message)
                    else:
                        result = await asyncio.to_thread(function, message)
                except Exception as exc:
                    log.exception(f"Handler {function.__name__} raised: {exc}")
                    continue

                if result is not None:
                    reply_payload = result
                    break

            if reply_payload is not None:
                # Build a REPLY message back to the original sender
                reply_qi_session = QiSession(
                    id=HUB_ID, logical_id=HUB_ID, parent_logical_id=None, tags=[]
                )
                reply_message = QiMessage(
                    message_id=str(uuid4()),
                    topic=message.topic,
                    type=QiMessageType.REPLY,
                    sender=reply_qi_session,
                    target=[message.sender.logical_id],
                    reply_to=message.message_id,
                    context=message.context,
                    payload=reply_payload,
                    bubble=False,
                )
                await self._fan_out(message=reply_message)
                return

            # If no handler returned a value, treat as an EVENT
            await self._fan_out(message=message)
            return

        # 2c) If it's an EVENT, fan out
        await self._fan_out(message=message)

    async def _fan_out(self, *, message: QiMessage) -> None:
        """
        Serialize `message` to JSON once, then send to all matching WebSockets.

        Lock usage:
          • If message.target is non‐empty, snapshot only those sessions under lock
          • If bubble=True, snapshot parent only
          • Otherwise, snapshot all sockets under lock

        Args:
            message: the QiMessage to deliver
        """
        raw_message = message.model_dump_json(exclude_none=True)

        # Determine which logical_ids to send to
        if message.target:
            # explicit targets
            logical_targets = message.target
        elif message.bubble and message.sender.parent_logical_id:
            logical_targets = [message.sender.parent_logical_id]
        else:
            logical_targets = []  # empty means "broadcast"

        if logical_targets:
            live_map = await self._connection_manager.snapshot_sessions_by_logical(
                logical_targets
            )
        else:
            live_map = await self._connection_manager.snapshot_sockets()

        if not live_map:
            return

        # Send to each socket concurrently under a TaskGroup
        async with asyncio.TaskGroup() as task_group:
            for socket in live_map.values():
                task_group.create_task(
                    self._safe_send(socket=socket, raw_message=raw_message)
                )

    async def _safe_send(self, *, socket: WebSocket, raw_message: str) -> None:
        """
        Attempt to send `raw_message` (string) on the WebSocket.
        Any exception (e.g. disconnected) is logged but not re‐raised.

        Args:
            socket:      the WebSocket to send to
            raw_message: serialized QiMessage JSON string
        """
        try:
            await socket.send_text(raw_message)
        except Exception:
            log.exception("Error sending message over WebSocket")
