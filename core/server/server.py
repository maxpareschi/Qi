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
    ws: WebSocket, session: str = None, window_uuid: str = None
):
    # Extract session and window_uuid from query parameters if not provided as path params
    if session is None:
        session = ws.query_params.get("session", "unknown")
    if window_uuid is None:
        window_uuid = ws.query_params.get("window_uuid")

    log.debug(
        f"🌐 WebSocket endpoint: session={session}, window_uuid={window_uuid[:8] if window_uuid else 'None'}..."
    )
    await qi_bus.connect(ws, session, window_uuid)


if qi_dev_mode:
    qi_server.add_middleware(QiDevProxyMiddleware)
    log.info("DevProxyMiddleware enabled")
else:
    qi_server.add_middleware(QiSPAStaticFilesMiddleware)


@qi_server.get("/")
async def root():
    return {"message": "Qi - Fastapi local server is running!"}
