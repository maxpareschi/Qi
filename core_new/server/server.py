"""
Server Manager for Qi.

This module provides a server manager for the FastAPI application.
"""

import asyncio
from typing import Optional

import uvicorn
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect

from core_new.abc import ManagerBase
from core_new.config import app_config
from core_new.di import container
from core_new.logger import get_logger
from core_new.models import QiMessage, QiSession

log = get_logger("server.server")


class ServerManager(ManagerBase):
    """
    Manager for the FastAPI server.

    This class provides a unified interface for starting and stopping the server,
    and for adding routes and middleware.
    """

    def __init__(self):
        """Initialize the server manager."""
        self.app = FastAPI(
            title="Qi Server",
            version="1.0.0",
            description="Qi Application Server",
        )
        self._server: Optional[uvicorn.Server] = None
        self._server_task: Optional[asyncio.Task] = None
        self._hub = None  # Will be set later to avoid circular imports
        self._setup_routes()

    def _get_hub(self):
        """
        Get the message hub.

        This method lazily loads the hub to avoid circular imports.

        Returns:
            The message hub.
        """
        if self._hub is None:
            self._hub = container.get("hub")
        return self._hub

    def _setup_routes(self):
        """Set up the basic routes for the server."""

        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {"message": "Qi Application Server"}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for client connections."""
            await websocket.accept()
            session: Optional[QiSession] = None

            try:
                # Receive the initial session data
                init_data = await websocket.receive_json()
                session = QiSession(**init_data)

                # Register the session with the hub
                hub = self._get_hub()
                await hub.register(websocket, session)
                log.info(f"WebSocket session registered: {session.id}")

                # Loop to receive messages
                async for raw_message in websocket.iter_json():
                    try:
                        message = QiMessage(**raw_message)
                        await hub.publish(message)
                    except Exception as e:
                        log.error(f"Error processing message: {e}")

            except WebSocketDisconnect:
                log.info(
                    f"WebSocket disconnected: {session.id if session else 'unknown'}"
                )
            except Exception as e:
                log.error(f"WebSocket error: {e}")
            finally:
                if session:
                    hub = self._get_hub()
                    await hub.unregister(session_id=session.id)
                    log.info(f"WebSocket session unregistered: {session.id}")

    def add_router(self, router: APIRouter) -> None:
        """
        Add a router to the FastAPI application.

        Args:
            router: The router to add.
        """
        self.app.include_router(router)

    @property
    def host(self) -> str:
        """Get the host to bind to."""
        return app_config.server.host

    @property
    def port(self) -> int:
        """Get the port to bind to."""
        return app_config.server.port

    async def initialize(self) -> None:
        """Initializes the server manager. A no-op for this manager."""
        pass

    async def start(self) -> None:
        """
        Start the server.

        This method starts the server in a background task.
        """
        log.info(f"Starting server on {self.host}:{self.port}")

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if app_config.dev_mode else "info",
            ssl_keyfile=app_config.server.ssl_key_path,
            ssl_certfile=app_config.server.ssl_cert_path,
        )

        self._server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(self._server.serve())

        log.info(f"Server started on {self.host}:{self.port}")

    async def shutdown(self) -> None:
        """
        Stop the server.

        This method stops the server if it is running.
        """
        if self._server is None:
            return

        log.info("Stopping server")

        # Signal the server to stop
        self._server.should_exit = True

        # Wait for the server to stop
        if self._server_task:
            try:
                await asyncio.wait_for(self._server_task, timeout=5.0)
            except asyncio.TimeoutError:
                log.warning("Server shutdown timed out. Forcing exit.")
                self._server_task.cancel()

        log.info("Server stopped")
        self._server = None
        self._server_task = None

    def get_url(self) -> str:
        """
        Get the URL of the server.

        Returns:
            The URL of the server.
        """
        protocol = "https" if app_config.server.use_ssl else "http"
        return f"{protocol}://{self.host}:{self.port}"


# Create a global server manager instance
server_manager = ServerManager()

# Register the server manager as a singleton service
container.register_instance("server", server_manager)
