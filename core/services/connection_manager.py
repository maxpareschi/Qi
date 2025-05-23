import asyncio
import collections
import fnmatch
import inspect
import json
from typing import Any, Callable, Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from core.services.log import log


class QiConnectionManager:
    """
    Singleton connection manager that combines:
    - WebSocket connection management
    - Event bus with pattern matching
    - Session-based message routing
    - Health checks and connection monitoring
    """

    def __init__(self):
        """Initialize the connection manager"""
        # Map of session_id -> set of WebSocket connections
        self._clients: Dict[str, Set[WebSocket]] = {}
        # Map of pattern -> set of handler functions
        self._handlers: Dict[str, Set[Callable]] = collections.defaultdict(set)
        # Health check task
        self._health_check_task = None

        log.info(f"Creating new ConnectionManager instance with ID: {id(self)}")

    async def connect(self, ws: WebSocket) -> None:
        """Accept a new WebSocket connection and handle messages"""
        # Extract session from query parameters
        session = None
        if "session" in ws.query_params:
            session = ws.query_params["session"]

        if not session:
            await ws.close(code=1008, reason="Session ID required as query parameter")
            return

        await ws.accept()

        try:
            # Register the client
            if session not in self._clients:
                self._clients[session] = set()
            self._clients[session].add(ws)

            # Notify successful connection
            await self._send_to_client(ws, "system.connected", {"session": session})

            # Start health check if not already running
            self._ensure_health_check()

            # Continue receiving messages
            while True:
                data = await ws.receive_json()
                if "topic" not in data:
                    continue

                topic = data["topic"]
                payload = data.get("payload", {})

                log.debug(f"Received message: {topic} with payload {payload}")

                # Don't echo messages back - process them and let handlers send responses
                await self._process_message(topic, payload, session)

        except WebSocketDisconnect:
            log.info(f"Client disconnected from session {session}")
        except Exception as e:
            log.error(f"WebSocket error: {str(e)}")
        finally:
            if session:
                # Clean up the connection
                self._remove_connection(session, ws)

    async def _send_to_client(self, ws: WebSocket, topic: str, payload: Any) -> None:
        """Send a message to a specific client"""
        try:
            await ws.send_text(json.dumps({"topic": topic, "payload": payload}))
        except Exception as e:
            log.error(f"Failed to send to client: {str(e)}")

    def _remove_connection(self, session: str, ws: WebSocket) -> None:
        """Remove a WebSocket connection from a session"""
        if session in self._clients:
            self._clients[session].discard(ws)
            if not self._clients[session]:
                del self._clients[session]

    def _ensure_health_check(self) -> None:
        """Ensure health check task is running"""
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        """Periodically check if connections are still alive"""
        try:
            while True:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._check_connections()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Health check error: {str(e)}")

    async def _check_connections(self) -> None:
        """Ping all connections to verify they're alive"""
        for session, connections in list(self._clients.items()):
            for ws in list(connections):
                try:
                    # Send a ping message
                    await self._send_to_client(
                        ws,
                        "system.ping",
                        {"timestamp": asyncio.get_event_loop().time()},
                    )
                except Exception:
                    # Connection is dead, remove it
                    self._remove_connection(session, ws)

    def subscribe(self, pattern: str) -> Callable:
        """
        Subscribe to a pattern with wildcards.
        Returns a decorator for registering handler functions.
        """
        pattern = pattern.strip()  # Remove any whitespace

        def decorator(handler: Callable) -> Callable:
            log.info(f"Registering handler for pattern: '{pattern}'")
            self._handlers[pattern].add(handler)
            return handler

        return decorator

    def list_handlers(self):
        """Debug method to list all registered handlers"""
        log.info(f"Registered handlers: {list(self._handlers.keys())}")
        for pattern, handlers in self._handlers.items():
            log.info(f"  L Pattern '{pattern}': {len(handlers)} handlers")
            for handler in handlers:
                log.info(f"    - {handler.__name__}")

        if not self._handlers:
            log.warning("No handlers registered!")

        return self._handlers

    def unsubscribe(self, pattern: str, handler: Callable) -> None:
        """Unsubscribe a handler from a pattern"""
        self._handlers.get(pattern, set()).discard(handler)

    async def _process_message(
        self, topic: str, payload: Any, session: Optional[str]
    ) -> None:
        """Process a message through pattern-matched handlers"""
        topic = topic.strip()  # Remove any whitespace
        log.info(
            f"Processing message: topic='{topic}', patterns={list(self._handlers.keys())}"
        )

        # Track tasks to wait for
        tasks = []
        handlers_called = 0

        # Try direct matching first (most common case)
        if topic in self._handlers:
            log.info(f"  Direct match found for topic '{topic}'")
            handlers = self._handlers[topic]

            for handler in list(handlers):
                try:
                    handlers_called += 1
                    log.info(
                        f"  Calling handler {handler.__name__} for topic '{topic}'"
                    )
                    if inspect.iscoroutinefunction(handler):
                        tasks.append(
                            asyncio.create_task(handler(topic, payload, session))
                        )
                    else:
                        handler(topic, payload, session)
                except Exception as e:
                    log.exception(f"Handler error: {str(e)}")
        else:
            # Try pattern matching for wildcards
            for pattern, handlers in self._handlers.items():
                if (
                    "*" in pattern or "?" in pattern
                ):  # Only use fnmatch for patterns with wildcards
                    matched = fnmatch.fnmatch(topic, pattern)
                    log.info(
                        f"  Checking wildcard pattern '{pattern}' against topic '{topic}': {'MATCHED' if matched else 'NOT MATCHED'}"
                    )

                    if matched:
                        log.info(
                            f"  Pattern '{pattern}' matched topic '{topic}' with {len(handlers)} handlers"
                        )

                        # Call each handler
                        for handler in list(handlers):
                            try:
                                handlers_called += 1
                                log.info(
                                    f"  Calling handler {handler.__name__} for topic '{topic}'"
                                )
                                if inspect.iscoroutinefunction(handler):
                                    tasks.append(
                                        asyncio.create_task(
                                            handler(topic, payload, session)
                                        )
                                    )
                                else:
                                    handler(topic, payload, session)
                            except Exception as e:
                                log.exception(f"Handler error: {str(e)}")

        if not handlers_called:
            log.warning(f"No handlers matched topic: '{topic}'")
            # Debug dump of all patterns for this topic
            log.warning(f"Available patterns: {list(self._handlers.keys())}")

        # Wait for async handlers to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def emit(
        self, topic: str, payload: Any = None, *, session: Optional[str] = None
    ) -> None:
        """
        Emit an event to subscribers and optionally to WebSocket clients.

        Args:
            topic: Event topic
            payload: Event data
            session: Optional session ID to send to
        """
        payload = payload or {}

        # First process through handlers
        await self._process_message(topic, payload, session)

        # Then send to WebSocket clients if session is specified
        if session:
            await self.push(topic, payload, session=session)

    def emit_sync(
        self, topic: str, payload: Any = None, *, session: Optional[str] = None
    ) -> None:
        """Fire-and-forget from sync context"""
        asyncio.create_task(self.emit(topic, payload, session=session))

    async def push(self, topic: str, payload: Any, *, session: str) -> None:
        """Send a message to all clients in a session"""
        if session not in self._clients:
            return

        log.info(f"Pushing message to session {session}: {topic}")
        message = json.dumps({"topic": topic, "payload": payload})
        dead_connections = []

        for ws in self._clients[session]:
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.append(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self._remove_connection(session, ws)


# Create a TRUE module-level singleton instance
# This ensures the same instance is used throughout the application
# no matter how it's imported
_instance = None


def get_connection_manager():
    """Get or create the singleton connection manager instance"""
    global _instance
    if _instance is None:
        _instance = QiConnectionManager()
        log.info(f"Created connection manager singleton with ID: {id(_instance)}")
    return _instance


# Expose the instance directly
connection_manager = get_connection_manager()

# For debugging: print the module name and instance ID
module_name = __name__
log.info(
    f"Connection manager module {module_name} loaded with instance ID: {id(connection_manager)}"
)


# FastAPI endpoint
async def websocket_endpoint(ws: WebSocket):
    await connection_manager.connect(ws)
