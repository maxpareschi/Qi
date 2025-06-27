"""
Server module.

This module provides FastAPI server with WebSocket support for real-time communication.
All messages flow through the EventBus service for proper session management and routing.
"""

import asyncio
import json
from typing import TYPE_CHECKING

import uvicorn
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.decorators import inject, service
from core.logger import get_logger
from core.models import QiMessage, QiMessageType, QiSession

if TYPE_CHECKING:
    from core.bus import EventBus
    from core.config import QiLaunchConfig
    from core.hub import Hub

log = get_logger(__name__)


@service("server")
@inject()
class ServerManager:
    """
    FastAPI server manager with WebSocket support.

    Provides:
    - HTTP API endpoints
    - WebSocket connections integrated with EventBus
    - Session management through EventBus
    """

    # Dependencies auto-injected by Hub based on attribute names
    config: "QiLaunchConfig"
    hub: "Hub"
    bus: "EventBus"

    def __init__(self):
        # Dependencies auto-injected by Hub after registration

        self.app = FastAPI(
            title="Qi Server",
            version="1.0.0",
            description="Qi Application Server with WebSocket support",
        )

        self._server: uvicorn.Server | None = None
        self._server_task: asyncio.Task | None = None

        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self):
        """Setup FastAPI middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/")
        async def root():
            return {"message": "Qi Server", "status": "running"}

        @self.app.get("/health")
        async def health():
            connection_count = self.bus.get_connection_count() if self.bus else 0
            return {"status": "healthy", "connections": connection_count}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, logical_id: str = "default"):
            await self._handle_websocket(websocket, logical_id)

    async def _handle_websocket(self, websocket: WebSocket, logical_id: str):
        """Handle WebSocket connection lifecycle."""
        await websocket.accept()

        session = None
        try:
            # Register session with EventBus
            session = await self.bus.register_session(websocket, logical_id)
            log.info(f"WebSocket session registered: {session.id} ({logical_id})")

            # Send welcome message
            welcome_msg = QiMessage(
                topic="session.welcome",
                type=QiMessageType.EVENT,
                sender=session,
                payload={"session_id": session.id, "logical_id": logical_id},
            )
            await self.bus.publish(welcome_msg)

            # Handle incoming messages
            while True:
                data = await websocket.receive_text()
                await self._handle_message(session, data)

        except WebSocketDisconnect:
            log.info(
                f"WebSocket session disconnected: {session.id if session else 'unknown'}"
            )
        except Exception as e:
            log.error(
                f"WebSocket error for session {session.id if session else 'unknown'}: {e}"
            )
        finally:
            # Cleanup session
            if session:
                # Send disconnect message
                disconnect_msg = QiMessage(
                    topic="session.disconnect",
                    type=QiMessageType.EVENT,
                    sender=session,
                    payload={"session_id": session.id},
                )
                await self.bus.publish(disconnect_msg)

                await self.bus.unregister_session(session.id)

    async def _handle_message(self, session: QiSession, message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)

            # Extract message components
            topic = data.get("topic")
            message_type = data.get("type", "event")
            payload = data.get("payload", {})
            target = data.get("target", [])
            reply_to = data.get("reply_to")

            if not topic:
                await self._send_error(session, "Missing topic in message")
                return

            # Create QiMessage
            qi_message = QiMessage(
                topic=topic,
                type=QiMessageType(message_type),
                sender=session,
                target=target,
                reply_to=reply_to,
                payload=payload,
            )

            # Publish through EventBus
            await self.bus.publish(qi_message)

        except json.JSONDecodeError:
            await self._send_error(session, "Invalid JSON in message")
        except ValueError as e:
            await self._send_error(session, f"Invalid message format: {str(e)}")
        except Exception as e:
            log.error(f"Error handling message from session {session.id}: {e}")
            await self._send_error(session, f"Server error: {str(e)}")

    async def _send_error(self, session: QiSession, error: str):
        """Send error message to session."""
        error_msg = QiMessage(
            topic="error",
            type=QiMessageType.EVENT,
            sender=session,  # Server responding as the session itself
            target=[session.id],
            payload={"error": error},
        )
        await self.bus.publish(error_msg)

    def add_router(self, router: APIRouter, prefix: str = "") -> None:
        """Add a router to the FastAPI app."""
        self.app.include_router(router, prefix=prefix)
        log.debug(f"Added router with prefix: {prefix}")

    async def start(self):
        """Start the server."""
        if not self.config:
            raise RuntimeError("Server not configured (config not injected)")

        server_config = uvicorn.Config(
            app=self.app,
            host=self.config.local_server.host,
            port=self.config.local_server.port,
            log_level="info" if self.config.dev_mode else "warning",
        )

        self._server = uvicorn.Server(server_config)

        # Start server in background task
        self._server_task = asyncio.create_task(self._server.serve())

        log.info(
            f"Server started on {self.config.local_server.host}:{self.config.local_server.port}"
        )

    async def shutdown(self):
        """Shutdown the server gracefully."""
        if self._server:
            self._server.should_exit = True

        if self._server_task:
            try:
                await asyncio.wait_for(self._server_task, timeout=10.0)
            except asyncio.TimeoutError:
                log.warning("Server shutdown timed out")
                self._server_task.cancel()

        log.info("Server shutdown complete")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._server_task is not None and not self._server_task.done()

    @property
    def url(self) -> str:
        """Get server URL."""
        if self.config:
            return f"http://{self.config.local_server.host}:{self.config.local_server.port}"
        return "http://localhost:8000"
