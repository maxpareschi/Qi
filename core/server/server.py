# main.py
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from core.bus import QiConnectionSource, QiMessageBus
from core.logger import get_logger
from core.server.middleware import (
    QiDevProxyMiddleware,
    QiSPAStaticFilesMiddleware,
)

log = get_logger(__name__)

qi_dev_mode: bool = os.getenv("QI_DEV_MODE", "0") == "1"


qi_server = FastAPI(
    title="Qi Core Server",
    version="1.0.0",
    description="WebSocket-based communication server for Qi framework.",
)


@qi_server.get("/")
async def root():
    return {"message": "Qi - Fastapi local server is running!"}


@qi_server.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    init = await ws.receive_json()
    try:
        source = QiConnectionSource(**init)
    except ValidationError:
        await ws.close(code=4401)
        return

    bus = QiMessageBus()

    try:
        await bus.connect(ws, source)
    except WebSocketDisconnect:
        log.debug(f"WebSocket disconnected: source={source}")
        bus._connections.unregister(bus._connections.by_source_id())
    except Exception as e:
        log.error(f"WebSocket error: {e}")


if qi_dev_mode:
    qi_server.add_middleware(QiDevProxyMiddleware)
    log.debug("Dev mode enabled: using QiDevProxyMiddleware for routing.")
else:
    qi_server.add_middleware(QiSPAStaticFilesMiddleware)
