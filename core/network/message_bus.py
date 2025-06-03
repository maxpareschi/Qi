from __future__ import annotations

import asyncio
import uuid
from asyncio import Future, TimeoutError
from collections import defaultdict
from typing import Any, Final

from fastapi import WebSocket

from core.bases.models import (
    QiHandler,
    QiMessage,
    QiMessageType,
    QiRequestTracker,
    QiSession,
)
from core.config import qi_config
from core.logger import get_logger
from core.network.connection_manager import QiConnectionManager
from core.network.handler_registry import QiHandlerRegistry

log = get_logger(__name__)

HUB_ID: Final = "__hub__"


class QiMessageBus:
    """
    Canonical API for socket & handler management **and** routing.
    """

    def __init__(self) -> None:
        self._connections: QiConnectionManager = QiConnectionManager()
        self._handler_registry: QiHandlerRegistry = QiHandlerRegistry()
        self._request_trackers: dict[str, QiRequestTracker] = {}
        self._session_to_pending_requests: defaultdict[str, set[str]] = defaultdict(set)

    async def register(self, socket: WebSocket, info: QiSession) -> None:
        await self._connections.register(socket, info)
        log.debug(f"Session registered: {info.logical_id}")

    async def unregister(self, session_id: str) -> None:
        await self._connections.unregister(session_id)
        await self._handler_registry.drop_session(session_id)

        # Cleanup pending requests initiated by the unregistering session
        request_ids_to_cancel = list(
            self._session_to_pending_requests.get(session_id, set())
        )
        for request_id in request_ids_to_cancel:
            tracker = self._cleanup_pending_request(request_id)
            if tracker and not tracker.reply_future.done():
                tracker.reply_future.cancel()

        # Ensure the session itself is removed from the index if somehow missed by cleanup
        self._session_to_pending_requests.pop(session_id, None)

        log.debug(f"Session unregistered: {session_id}")

    def on(self, topic: str, *, session_id: str = HUB_ID):
        def _decorator(function: QiHandler):
            if not callable(function):
                raise ValueError(f"Handler must be callable, got {type(function)}")
            asyncio.create_task(
                self._handler_registry.register(
                    function, topic=topic, session_id=session_id
                )
            )
            return function

        return _decorator

    async def publish(self, message: QiMessage) -> None:
        if message.topic.startswith("hub.") and message.sender.logical_id != HUB_ID:
            log.warning(f"Unauthorised publish to {message.topic}")
            return

        if message.type is QiMessageType.REPLY and message.reply_to:
            tracker = self._cleanup_pending_request(
                message.reply_to
            )  # reply_to is the original request_id
            if tracker and not tracker.reply_future.done():
                tracker.reply_future.set_result(message.payload)
            return

        reply_payload = await self._handler_registry.dispatch(message)
        if message.type is QiMessageType.REQUEST and reply_payload is not None:
            reply_message = QiMessage(
                topic=message.topic,
                type=QiMessageType.REPLY,
                sender=QiSession(id=HUB_ID, logical_id=HUB_ID),
                target=[message.sender.logical_id],
                reply_to=message.message_id,  # original request_id
                payload=reply_payload,
            )
            await self._fan_out(reply_message)
            return
        await self._fan_out(message)

    async def request(
        self,
        topic: str,
        *,
        payload: Any,
        sender: QiSession,
        target: list[str] | None = None,
        bubble: bool = False,
        timeout: float = qi_config.reply_timeout,
    ) -> Any:
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        if timeout > 300:
            raise ValueError("Timeout cannot exceed 300 seconds")

        request_id = str(uuid.uuid4())  # This is the ID for the request we are sending
        reply_future: Future = asyncio.get_running_loop().create_future()

        self._request_trackers[request_id] = QiRequestTracker(
            reply_future=reply_future,
            requesting_session_id=sender.id,  # Store the unique session.id
        )
        self._session_to_pending_requests[sender.id].add(request_id)

        try:
            await self.publish(
                QiMessage(
                    message_id=request_id,  # Use the generated request_id for this message
                    topic=topic,
                    type=QiMessageType.REQUEST,
                    sender=sender,
                    target=target or [],
                    bubble=bubble,
                    payload=payload,
                )
            )
            return await asyncio.wait_for(reply_future, timeout)
        except TimeoutError as e:
            tracker = self._cleanup_pending_request(request_id)
            # Future might already be cancelled by unregister, or not done
            if tracker and not tracker.reply_future.done():
                tracker.reply_future.set_exception(
                    e
                )  # Propagate timeout to the awaiter
            raise TimeoutError(
                f"No reply to request {topic!r} (id: {request_id}) within {timeout}s"
            ) from e
        except Exception as e:
            tracker = self._cleanup_pending_request(request_id)
            if tracker and not tracker.reply_future.done():
                tracker.reply_future.set_exception(e)  # Propagate other exceptions
            raise

    async def _fan_out(self, message: QiMessage) -> None:
        raw_message = message.model_dump_json()
        destinations = await self._resolve_destinations(message)
        sockets = await asyncio.gather(
            *(self._connections.get_socket(session_id) for session_id in destinations),
            return_exceptions=True,
        )
        await asyncio.gather(
            *(
                self._safe_send(socket, raw_message)
                for socket in sockets
                if isinstance(socket, WebSocket)
            ),
            return_exceptions=True,
        )

    async def _resolve_destinations(self, message: QiMessage) -> list[str]:
        if message.target:
            return await self._connections.get_multiple_session_ids(message.target)
        elif message.bubble and message.sender.parent_logical_id:
            parent_session = await self._connections.get_live_session_id(
                message.sender.parent_logical_id
            )
            return [parent_session] if parent_session else []
        else:
            all_logical_ids = await self._connections.get_all_logical_ids()
            if message.sender.logical_id in all_logical_ids:
                all_logical_ids.remove(message.sender.logical_id)
            return await self._connections.get_multiple_session_ids(all_logical_ids)

    def _cleanup_pending_request(self, request_id: str) -> QiRequestTracker | None:
        """Atomically removes a request tracker and its session linkage."""
        tracker = self._request_trackers.pop(request_id, None)
        if tracker:
            session_requests = self._session_to_pending_requests.get(
                tracker.requesting_session_id
            )
            if session_requests:
                session_requests.discard(request_id)
                if not session_requests:  # If set becomes empty, remove session entry
                    self._session_to_pending_requests.pop(
                        tracker.requesting_session_id, None
                    )
        return tracker

    async def _safe_send(self, socket: WebSocket | None, raw_message: str) -> None:
        if not socket:
            return
        try:
            await socket.send_text(raw_message)
        except Exception as e:
            log.error(f"Failed to send message: {e}")
