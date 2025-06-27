"""
Event Bus module.

This module provides the EventBus service that handles session management,
message routing, and event handling based on the QiMessage envelope structure.
"""

import asyncio
import inspect
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import WebSocket

from core.decorators import inject, service
from core.logger import get_logger
from core.models import QiHandler, QiMessage, QiMessageType, QiSession

if TYPE_CHECKING:
    from core.config import QiLaunchConfig

log = get_logger(__name__)


@service("bus")
@inject()
class EventBus:
    """
    Message bus service for routing messages between sessions.

    Responsibilities:
    - Session management (WebSocket connections)
    - Handler registration and routing
    - Message envelope processing
    - Connection lifecycle management
    """

    # Dependencies auto-injected by Hub based on attribute names
    config: "QiLaunchConfig"

    def __init__(self):
        # Dependencies auto-injected by Hub after registration

        # Session management
        self.sessions: dict[str, QiSession] = {}  # session_id -> QiSession
        self.connections: dict[str, WebSocket] = {}  # session_id -> WebSocket
        self.logical_to_sessions: dict[
            str, list[str]
        ] = {}  # logical_id -> [session_ids]

        # Handler registry
        self.handlers: dict[str, list[QiHandler]] = {}  # topic -> [handlers]
        self.session_handlers: dict[
            str, dict[str, list[QiHandler]]
        ] = {}  # session_id -> topic -> [handlers]

        self._lock = asyncio.Lock()

    async def register_session(
        self,
        websocket: WebSocket,
        logical_id: str,
        parent_logical_id: str | None = None,
        tags: list[str] | None = None,
    ) -> QiSession:
        """
        Register a new session with WebSocket connection.

        Args:
            websocket: The WebSocket connection
            logical_id: User-defined logical identifier
            parent_logical_id: Optional parent session ID
            tags: Optional list of tags

        Returns:
            The created QiSession
        """
        async with self._lock:
            session = QiSession(
                logical_id=logical_id,
                parent_logical_id=parent_logical_id,
                tags=tags or [],
            )

            self.sessions[session.id] = session
            self.connections[session.id] = websocket

            # Track by logical_id
            if logical_id not in self.logical_to_sessions:
                self.logical_to_sessions[logical_id] = []
            self.logical_to_sessions[logical_id].append(session.id)

            log.info(f"Registered session {session.id} with logical_id '{logical_id}'")
            return session

    async def unregister_session(self, session_id: str) -> None:
        """
        Unregister a session and clean up resources.

        Args:
            session_id: The session ID to unregister
        """
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return

            # Remove from sessions
            del self.sessions[session_id]
            self.connections.pop(session_id, None)

            # Remove from logical mapping
            logical_sessions = self.logical_to_sessions.get(session.logical_id, [])
            if session_id in logical_sessions:
                logical_sessions.remove(session_id)
                if not logical_sessions:
                    del self.logical_to_sessions[session.logical_id]

            # Remove session-specific handlers
            self.session_handlers.pop(session_id, None)

            log.info(f"Unregistered session {session_id}")

    def register_handler(
        self, topic: str, handler: QiHandler, session_id: str | None = None
    ) -> None:
        """
        Register a message handler for a topic.

        Args:
            topic: The topic to handle
            handler: The handler function
            session_id: Optional session ID for session-specific handlers
        """
        if session_id:
            # Session-specific handler
            if session_id not in self.session_handlers:
                self.session_handlers[session_id] = {}
            if topic not in self.session_handlers[session_id]:
                self.session_handlers[session_id][topic] = []
            self.session_handlers[session_id][topic].append(handler)
            log.debug(f"Registered session handler for {topic} in session {session_id}")
        else:
            # Global handler
            if topic not in self.handlers:
                self.handlers[topic] = []
            self.handlers[topic].append(handler)
            log.debug(f"Registered global handler for {topic}")

    async def publish(self, message: QiMessage) -> None:
        """
        Publish a message to registered handlers and route to target sessions.

        Args:
            message: The message to publish
        """
        # Handle locally registered handlers first
        await self._dispatch_to_handlers(message)

        # Route to target sessions if specified
        if message.target:
            await self._route_to_targets(message)

    async def _dispatch_to_handlers(self, message: QiMessage) -> None:
        """Dispatch message to registered handlers."""
        tasks = []

        # Global handlers
        global_handlers = self.handlers.get(message.topic, [])
        for handler in global_handlers:
            tasks.append(self._call_handler(handler, message))

        # Session-specific handlers for sender
        sender_handlers = self.session_handlers.get(message.sender.id, {}).get(
            message.topic, []
        )
        for handler in sender_handlers:
            tasks.append(self._call_handler(handler, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _call_handler(self, handler: QiHandler, message: QiMessage) -> Any:
        """Safely call a message handler."""
        try:
            if inspect.iscoroutinefunction(handler):
                return await handler(message)
            else:
                return await asyncio.to_thread(handler, message)
        except Exception as e:
            log.error(
                f"Error in handler {handler.__name__} for topic {message.topic}: {e}"
            )
            return None

    async def _route_to_targets(self, message: QiMessage) -> None:
        """Route message to target sessions via WebSocket."""
        for target in message.target:
            # Check if target is a session ID
            if target in self.connections:
                await self._send_to_session(target, message)
            # Check if target is a logical ID
            elif target in self.logical_to_sessions:
                session_ids = self.logical_to_sessions[target]
                for session_id in session_ids:
                    await self._send_to_session(session_id, message)
            else:
                log.warning(
                    f"Target '{target}' not found for message {message.message_id}"
                )

    async def _send_to_session(self, session_id: str, message: QiMessage) -> None:
        """Send message to a specific session via WebSocket."""
        websocket = self.connections.get(session_id)
        if not websocket:
            log.warning(f"No WebSocket connection for session {session_id}")
            return

        try:
            message_data = message.model_dump_json()
            await websocket.send_text(message_data)
            log.debug(f"Sent message {message.message_id} to session {session_id}")
        except Exception as e:
            log.error(f"Error sending message to session {session_id}: {e}")
            # Connection might be broken, let the connection manager handle cleanup

    async def request(
        self,
        topic: str,
        payload: dict[str, Any],
        sender: QiSession,
        target: list[str] | None = None,
        timeout: float = 5.0,
    ) -> Any:
        """
        Send a request message and wait for reply.

        Args:
            topic: The topic for the request
            payload: The request payload
            sender: The session making the request
            target: Optional target sessions
            timeout: Timeout for reply

        Returns:
            The reply payload
        """
        request_id = str(uuid4())

        message = QiMessage(
            message_id=request_id,
            topic=topic,
            type=QiMessageType.REQUEST,
            sender=sender,
            target=target or [],
            payload=payload,
            reply_to=request_id,
        )

        # Create reply future
        reply_future = asyncio.Future()

        # Register temporary handler for reply
        async def reply_handler(reply_msg: QiMessage):
            if reply_msg.reply_to == request_id:
                if not reply_future.done():
                    reply_future.set_result(reply_msg.payload)

        self.register_handler(f"{topic}.reply", reply_handler)

        try:
            # Send request
            await self.publish(message)

            # Wait for reply
            return await asyncio.wait_for(reply_future, timeout=timeout)

        except asyncio.TimeoutError:
            log.warning(f"Request {request_id} timed out after {timeout}s")
            raise
        finally:
            # Clean up temporary handler
            topic_handlers = self.handlers.get(f"{topic}.reply", [])
            if reply_handler in topic_handlers:
                topic_handlers.remove(reply_handler)

    def get_session(self, session_id: str) -> QiSession | None:
        """Get session by ID."""
        return self.sessions.get(session_id)

    def get_sessions_by_logical_id(self, logical_id: str) -> list[QiSession]:
        """Get all sessions with a specific logical ID."""
        session_ids = self.logical_to_sessions.get(logical_id, [])
        return [self.sessions[sid] for sid in session_ids if sid in self.sessions]

    def list_sessions(self) -> list[QiSession]:
        """List all active sessions."""
        return list(self.sessions.values())

    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.connections)
