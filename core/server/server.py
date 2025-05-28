# main.py
import os
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from core import logger
from core.bus import QiEventBus
from core.server.middleware import (
    QiDevProxyMiddleware,
    QiSPAStaticFilesMiddleware,
)

log = logger.get_logger(__name__)

qi_dev_mode: bool = os.getenv("QI_DEV_MODE", "0") == "1"


async def websocket_handler(
    websocket: WebSocket, session_id: str, window_id: Optional[str] = None
):
    """Handle WebSocket connections for real-time communication."""

    # Get the singleton bus instance
    bus = QiEventBus()

    try:
        log.debug(
            f"WebSocket connection: session={session_id[:8]}..., window={window_id[:8] if window_id else 'default'}..."
        )
        await bus.connect(websocket, session_id, window_id)
    except WebSocketDisconnect:
        log.debug(f"WebSocket disconnected: session={session_id[:8]}...")
    except Exception as e:
        log.error(f"WebSocket error: {e}")


def create_server() -> FastAPI:
    """Create and configure the FastAPI server."""

    app = FastAPI(
        title="Qi Core Server",
        version="1.0.0",
        description="WebSocket-based communication server for Qi framework.",
    )

    @app.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket, session_id: str, window_id: Optional[str] = None
    ):
        await websocket_handler(websocket, session_id, window_id)

    @app.get("/")
    async def root():
        return {"message": "Qi - Fastapi local server is running!"}

    return app


qi_server = create_server()


if qi_dev_mode:
    qi_server.add_middleware(QiDevProxyMiddleware)
    log.debug("Dev mode enabled: using QiDevProxyMiddleware for routing.")
else:
    qi_server.add_middleware(QiSPAStaticFilesMiddleware)
