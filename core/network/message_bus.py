from __future__ import annotations

import asyncio
import uuid
from asyncio import Future, TimeoutError
from typing import Any, Final

from fastapi import WebSocket

from core.bases.models import QiHandler, QiMessage, QiMessageType, QiSession
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
        self._pending_replies: dict[str, Future] = {}  # message_id → Future

    async def register(self, socket: WebSocket, info: QiSession) -> None:
        await self._connections.register(socket, info)
        # No system message - just log
        log.debug(f"Session registered: {info.logical_id}")

    async def unregister(self, session_id: str) -> None:
        await self._connections.unregister(session_id)
        await self._handler_registry.drop_session(session_id)

        # Clean up any pending replies from this session
        expired_replies = [
            message_id
            for message_id, future in self._pending_replies.items()
            if not future.done()
        ]
        for message_id in expired_replies:
            future = self._pending_replies.pop(message_id, None)
            if future and not future.done():
                future.cancel()

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
        # guard privileged topics
        if message.topic.startswith("hub.") and message.sender.logical_id != HUB_ID:
            log.warning(f"unauthorised publish to {message.topic}")
            return

        # reply short-circuit
        if (
            message.type is QiMessageType.REPLY
            and message.reply_to in self._pending_replies
        ):
            expected_reply = self._pending_replies.pop(message.reply_to)
            if not expected_reply.done():
                expected_reply.set_result(message.payload)
            return

        # dispatch to python handlers
        reply_payload = await self._handler_registry.dispatch(message)

        # if it was a REQUEST and any handler returned, craft auto-reply
        if message.type is QiMessageType.REQUEST and reply_payload is not None:
            reply_message = QiMessage(
                topic=message.topic,
                type=QiMessageType.REPLY,
                sender=QiSession(id=HUB_ID, logical_id=HUB_ID),
                target=[message.sender.logical_id],
                reply_to=message.message_id,
                payload=reply_payload,
            )
            await self._fan_out(reply_message)
            return

        # fan-out event or request without local reply
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
            raise ValueError("timeout must be positive")
        if timeout > 300:  # 5 minutes max
            raise ValueError("timeout cannot exceed 300 seconds")

        message_id = str(uuid.uuid4())
        expected_reply: Future = asyncio.get_running_loop().create_future()
        self._pending_replies[message_id] = expected_reply

        try:
            await self.publish(
                QiMessage(
                    message_id=message_id,
                    topic=topic,
                    type=QiMessageType.REQUEST,
                    sender=sender,
                    target=target or [],
                    bubble=bubble,
                    payload=payload,
                )
            )

            return await asyncio.wait_for(expected_reply, timeout)
        except TimeoutError as e:
            self._pending_replies.pop(message_id, None)
            raise TimeoutError(
                f"no reply to request {topic!r} within {timeout}s"
            ) from e
        except Exception:
            # Clean up on any error
            self._pending_replies.pop(message_id, None)
            if not expected_reply.done():
                expected_reply.cancel()
            raise

    async def _fan_out(self, message: QiMessage) -> None:
        raw_message = message.model_dump_json()
        destinations = await self._resolve_destinations(message)

        # Get all sockets in one batch for thread safety
        sockets = await asyncio.gather(
            *(self._connections.get_socket(session_id) for session_id in destinations),
            return_exceptions=True,
        )

        # Send to all valid sockets
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
            # Direct targeting - O(k) where k = target list size
            return await self._connections.get_multiple_session_ids(message.target)
        elif message.bubble and message.sender.parent_logical_id:
            # Bubble to parent - O(1)
            parent_session = await self._connections.get_live_session_id(
                message.sender.parent_logical_id
            )
            return [parent_session] if parent_session else []
        else:
            # Broadcast - get all but exclude sender
            all_logical_ids = await self._connections.get_all_logical_ids()
            if message.sender.logical_id in all_logical_ids:
                all_logical_ids.remove(
                    message.sender.logical_id
                )  # O(n) but simpler than filter
            return await self._connections.get_multiple_session_ids(all_logical_ids)

    async def _safe_send(self, socket: WebSocket | None, raw_message: str) -> None:
        if not socket:
            return
        try:
            await socket.send_text(raw_message)
        except Exception as e:  # noqa: BLE001
            log.error(f"failed to send message: {e}")
