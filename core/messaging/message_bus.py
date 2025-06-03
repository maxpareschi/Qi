from __future__ import annotations

import asyncio
import uuid
from asyncio import Future, TimeoutError
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Final

from fastapi import WebSocket

from core.bases.models import (
    QiHandler,
    QiMessage,
    QiMessageType,
    QiSession,
)
from core.config import qi_config
from core.constants import HUB_ID
from core.logging import get_logger
from core.messaging.connection_manager import QiConnectionManager
from core.messaging.handler_registry import QiHandlerRegistry

log = get_logger(__name__)


@dataclass
class RequestFuture:
    """
    Tracks an outgoing request, its reply future, and the originating session.
    Internal to QiMessageBus for managing pending requests.
    """

    reply_future: Future
    requesting_session_id: str


class PendingRequestLimitExceededError(Exception):
    """Exception raised when a session attempts to create too many pending requests."""

    pass


class QiMessageBus:
    """
    Core component for managing WebSocket sessions, message handlers, and message routing.

    This bus is responsible for:
    - Registering and unregistering client sessions (via QiConnectionManager).
    - Registering and unregistering message handlers for specific topics (via QiHandlerRegistry).
    - Tracking pending outgoing requests and their corresponding reply Futures.
    - Dispatching incoming messages to appropriate handlers or resolving pending requests.
    - Fanning out messages to relevant WebSocket connections.
    All operations modifying shared state are protected by an asyncio.Lock.
    """

    def __init__(self) -> None:
        """Initializes the QiMessageBus with connection manager, handler registry, and request tracking structures."""
        self._connections: QiConnectionManager = QiConnectionManager()
        self._handler_registry: QiHandlerRegistry = QiHandlerRegistry()
        self._request_futures: dict[str, RequestFuture] = {}
        self._session_to_pending_requests: defaultdict[str, set[str]] = defaultdict(set)
        self._lock: Final = asyncio.Lock()
        self.max_pending_requests_per_session = 100
        try:
            self.max_pending_requests_per_session = (
                qi_config.max_pending_requests_per_session
            )
        except AttributeError:
            log.warning(
                "qi_config.max_pending_requests_per_session not set, defaulting to 100."
            )
        # Default is set prior to try-except, so no else needed here.

    async def register(self, socket: WebSocket, info: QiSession) -> None:
        """
        Registers a new WebSocket connection and session with the connection manager.

        Args:
            socket: The FastAPI WebSocket object.
            info: The QiSession data for the new session.
        """
        await self._connections.register(socket, info)
        log.debug(f"Session registered: {info.logical_id} (id: {info.id})")

    async def unregister(self, session_id: str) -> None:
        """
        Unregisters a session by its unique session ID.

        This involves:
        - Unregistering from the connection manager (which closes the WebSocket).
        - Dropping all handlers associated with this session from the handler registry.
        - Cleaning up and canceling any pending requests initiated by this session.

        Args:
            session_id: The unique ID of the session to unregister.
        """
        await self._connections.unregister(session_id)
        await self._handler_registry.drop_session(session_id)

        async with self._lock:
            request_ids_to_cancel = list(
                self._session_to_pending_requests.get(session_id, set())
            )
            for request_id in request_ids_to_cancel:
                request_future = self._cleanup_pending_request(request_id)
                if request_future and not request_future.reply_future.done():
                    request_future.reply_future.cancel()
            self._session_to_pending_requests.pop(session_id, None)

        log.debug(f"Session unregistered: {session_id}")

    def on(self, topic: str, *, session_id: str = HUB_ID):
        """
        Decorator to register a message handler for a specific topic.

        Handlers are registered with the QiHandlerRegistry.
        By default, handlers are associated with the `HUB_ID` session, meaning they are
        not tied to a specific client connection's lifecycle unless a `session_id` is provided.

        Args:
            topic: The message topic to subscribe the handler to.
            session_id: The session ID to associate with this handler. Defaults to `HUB_ID`.

        Returns:
            A decorator function for registering the QiHandler.

        Raises:
            ValueError: If the provided handler is not callable.

        NOTE: For CPU-bound vs IO-bound operations:
            - Use async handlers for I/O-bound work
            - Use @cpu_bound decorator for CPU-intensive tasks
            - Sync handlers should complete in <100ms
        check perf metrics on logs to ensure handlers are efficient
        """

        def _decorator(function: QiHandler):
            if not callable(function):
                raise ValueError(f"Handler must be callable, got {type(function)}")
            # Registration is an async operation, create a task for it.
            asyncio.create_task(
                self._handler_registry.register(
                    function, topic=topic, session_id=session_id
                )
            )
            return function

        return _decorator

    async def publish(self, message: QiMessage) -> None:
        """
        Processes and routes an incoming QiMessage.

        - If the message is a REPLY, it attempts to resolve a pending request future.
        - If the message is a REQUEST, it dispatches to handlers and if a reply payload is
          generated, sends that reply back to the original sender.
        - For other messages (e.g., EVENT), it dispatches to handlers and fans out the original message.
        - Protects against unauthorized publishing to "hub." topics.

        Args:
            message: The QiMessage object to process.
        """
        if message.type is QiMessageType.REPLY and message.reply_to:
            request_future: RequestFuture | None = None
            async with self._lock:
                request_future = self._cleanup_pending_request(message.reply_to)

                if request_future and not request_future.reply_future.done():
                    request_future.reply_future.set_result(message.payload)
                elif not request_future:
                    log.warning(
                        f"Received reply for unknown or already handled request_id: {message.reply_to}"
                    )
            return  # Reply message processing stops here

        # For non-reply messages or if reply was for an unknown request, dispatch to handlers.
        reply_payload = await self._handler_registry.dispatch(message)

        if message.type is QiMessageType.REQUEST and reply_payload is not None:
            # If it was a request and a handler returned a payload, send it as a reply.
            reply_message = QiMessage(
                topic=message.topic,  # Reply can use the same topic or a specific reply topic
                type=QiMessageType.REPLY,
                sender=QiSession(id=HUB_ID, logical_id=HUB_ID),  # Reply is from the Hub
                target=[
                    message.sender.logical_id
                ],  # Target original sender's logical_id
                reply_to=message.message_id,  # Link to the original request's message_id
                context=message.context,  # Can optionally carry forward context
                payload=reply_payload,
            )
            await self._fan_out(reply_message)
            return  # Request processing stops here if a reply was sent by the bus

        # For events, or requests that did not yield an immediate reply from a handler
        # (e.g., if they are to be handled by other services that will send their own replies later),
        # fan out the original message.
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
        """
        Sends a message of type REQUEST and waits for a reply.

        A unique `request_id` is generated and tracked. The method waits for a
        corresponding REPLY message or until the timeout is reached.

        Args:
            topic: The topic for the request.
            payload: The payload for the request message.
            sender: The QiSession initiating the request.
            target: Optional list of logical_ids to target the request to.
            bubble: If True, the request may bubble up if not handled at the initial level.
            timeout: Maximum time in seconds to wait for a reply.
                     Defaults to `qi_config.reply_timeout`.

        Returns:
            The payload from the reply message.

        Raises:
            ValueError: If timeout is not positive or exceeds 300 seconds.
            PendingRequestLimitExceededError: If the sender's session has too many pending requests.
            TimeoutError: If no reply is received within the specified timeout.
            Any other exception that might occur during publishing or future resolution.
        """
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        if timeout > 300:  # 5 minutes max
            raise ValueError("Timeout cannot exceed 300 seconds")

        request_id = str(uuid.uuid4())
        reply_future: Future = asyncio.get_running_loop().create_future()

        async with self._lock:
            if (
                len(self._session_to_pending_requests[sender.id])
                >= self.max_pending_requests_per_session
            ):
                log.error(
                    f"Session {sender.id} (logical: {sender.logical_id}) exceeded pending request limit of {self.max_pending_requests_per_session}."
                )
                raise PendingRequestLimitExceededError(
                    f"Session {sender.id} exceeded pending request limit of {self.max_pending_requests_per_session}."
                )

            self._request_futures[request_id] = RequestFuture(
                reply_future=reply_future,
                requesting_session_id=sender.id,
            )
            self._session_to_pending_requests[sender.id].add(request_id)

        try:
            # The message_id of this outgoing request message is our generated request_id
            await self.publish(
                QiMessage(
                    message_id=request_id,
                    topic=topic,
                    type=QiMessageType.REQUEST,
                    sender=sender,
                    target=target or [],
                    bubble=bubble,
                    payload=payload,
                    # context can be passed here if needed from sender
                )
            )
            return await asyncio.wait_for(reply_future, timeout)
        except TimeoutError as e:
            request_future_obj: RequestFuture | None = None
            async with self._lock:
                request_future_obj = self._cleanup_pending_request(request_id)

            if request_future_obj and not request_future_obj.reply_future.done():
                request_future_obj.reply_future.set_exception(e)
            log.warning(
                f"No reply to request {topic!r} (id: {request_id}) for session {sender.logical_id} within {timeout}s"
            )
            raise TimeoutError(
                f"No reply to request {topic!r} (id: {request_id}) within {timeout}s"
            ) from e
        except Exception as e:
            # Catch-all for other exceptions during publish or wait_for
            # Ensure cleanup if an error occurs before or during waiting for the future
            request_future_obj: RequestFuture | None = None
            async with self._lock:
                request_future_obj = self._cleanup_pending_request(request_id)

            if request_future_obj and not request_future_obj.reply_future.done():
                # If the future hasn't been resolved by some other means (e.g. cancelled in unregister)
                # set this exception on it.
                request_future_obj.reply_future.set_exception(e)
            raise  # Re-raise the original exception

    async def _fan_out(self, message: QiMessage) -> None:
        """
        Sends a message to all relevant WebSocket connections based on message target or broadcast.

        Args:
            message: The QiMessage to fan out.
        """
        raw_message = message.model_dump_json()
        destinations = await self._resolve_destinations(message)

        # Gather tasks for getting sockets to allow concurrent fetching if needed in future
        socket_tasks = [
            self._connections.get_socket(session_id) for session_id in destinations
        ]
        sockets_results = await asyncio.gather(*socket_tasks, return_exceptions=True)

        # Gather tasks for sending messages
        send_tasks = []
        for i, res in enumerate(sockets_results):
            if isinstance(res, WebSocket):
                send_tasks.append(self._safe_send(res, raw_message))
            elif isinstance(res, Exception):
                log.error(
                    f"Error retrieving socket for session_id '{destinations[i]}' during fan_out: {res}"
                )
            # If res is None (socket not found), it's silently ignored here as get_socket can return None.

        if send_tasks:
            await asyncio.gather(
                *send_tasks, return_exceptions=True
            )  # Errors in _safe_send are logged there

    async def _resolve_destinations(self, message: QiMessage) -> list[str]:
        """
        Determines the list of target session_ids for a message.

        - If `message.target` is specified, those logical_ids are resolved to session_ids.
        - If `message.bubble` is True and `message.sender.parent_logical_id` exists,
          targets the parent session.
        - Otherwise (default broadcast behavior), targets all connected sessions except the sender.

        Args:
            message: The QiMessage for which to resolve destinations.

        Returns:
            A list of unique session_ids to send the message to.
        """
        if message.target:
            # Resolve logical_ids in target list to actual session_ids
            return await self._connections.get_multiple_session_ids(message.target)
        elif message.bubble and message.sender.parent_logical_id:
            # Target the parent session if bubble is True and parent exists
            parent_session_id = await self._connections.get_live_session_id(
                message.sender.parent_logical_id
            )
            return [parent_session_id] if parent_session_id else []
        else:
            # Default: broadcast to all except sender
            all_logical_ids = await self._connections.get_all_logical_ids()
            # Avoid sending message back to its own sender in a general broadcast
            try:
                all_logical_ids.remove(message.sender.logical_id)
            except ValueError:
                pass  # Sender's logical_id was not in the list (e.g. HUB_ID or not yet fully registered)
            return await self._connections.get_multiple_session_ids(all_logical_ids)

    def _cleanup_pending_request(self, request_id: str) -> RequestFuture | None:
        """
        Atomically removes a request future object and its session linkage from tracking.
        This method MUST be called while holding `self._lock`.

        Args:
            request_id: The ID of the request to clean up.

        Returns:
            The RequestFuture object if found and removed, otherwise None.
        """
        # Assumes lock is already held by the caller.
        request_future = self._request_futures.pop(request_id, None)
        if request_future:
            session_requests = self._session_to_pending_requests.get(
                request_future.requesting_session_id
            )
            if session_requests:
                session_requests.discard(request_id)
                if not session_requests:  # If set becomes empty, remove session entry
                    self._session_to_pending_requests.pop(
                        request_future.requesting_session_id, None
                    )
        return request_future

    async def _safe_send(self, socket: WebSocket | None, raw_message: str) -> None:
        """
        Safely sends a raw JSON string message over a WebSocket.
        Logs errors if sending fails but does not propagate exceptions.

        Args:
            socket: The WebSocket to send the message to. If None, does nothing.
            raw_message: The raw JSON string to send.
        """
        if not socket:
            return
        try:
            await socket.send_text(raw_message)
        except Exception as e:
            # Log error, but don't let one failed send stop others in a fan_out
            log.error(f"Failed to send message via WebSocket: {e}")
