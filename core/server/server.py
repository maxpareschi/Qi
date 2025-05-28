# main.py
import os

from fastapi import FastAPI, WebSocket

from core import logger
from core.server.bus import qi_bus
from core.server.middleware import (
    QiDevProxyMiddleware,
    QiSPAStaticFilesMiddleware,
)

log = logger.get_logger(__name__)
qi_dev_mode = os.getenv("QI_DEV_MODE", "0") == "1"

qi_server = FastAPI()


@qi_server.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket, session_id: str = None, window_id: str = None
):
    # Extract session_id and window_id from query parameters if not provided as path params
    if not session_id:
        session_id = ws.query_params.get("session_id")
    if not window_id:
        window_id = ws.query_params.get("window_id")

    if not session_id:
        await ws.close(code=4000, reason="session_id parameter required")
        return

    log.info(
        f"WebSocket connection request: session_id={session_id}, window_id={window_id}"
    )
    await qi_bus.connect(ws, session_id, window_id)


if qi_dev_mode:
    qi_server.add_middleware(QiDevProxyMiddleware)
    log.info("DevProxyMiddleware enabled")
else:
    qi_server.add_middleware(QiSPAStaticFilesMiddleware)


@qi_server.get("/")
async def root():
    return {"message": "Qi - Fastapi local server is running!"}
