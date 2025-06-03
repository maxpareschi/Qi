# main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from core.bases.models import QiMessage, QiSession
from core.config import qi_config
from core.logger import get_logger
from core.network.hub import hub
from core.server.middleware import (
    QiDevProxyMiddleware,
    QiSPAStaticFilesMiddleware,
)

log = get_logger(__name__)


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

    try:
        init = await ws.receive_json()
        session = QiSession.model_validate(init)
        await hub.register(ws, session)
    except ValidationError as e:
        log.warning(f"Invalid session data: {e}")
        await ws.close(code=4401)
        return
    except Exception as e:
        log.error(f"Session registration failed: {e}")
        await ws.close(code=4500)
        return

    try:
        async for raw_json in ws.iter_json():
            try:
                message = QiMessage.model_validate(raw_json)
                await hub.publish(message)
            except ValidationError as e:
                log.warning(f"Invalid message from {session.id}: {e}")
                # Continue processing other messages
            except Exception as e:
                log.error(f"Message processing error: {e}")
    except WebSocketDisconnect:
        log.debug(f"WebSocket disconnected: session={session.id}")
    except Exception as e:
        log.error(f"WebSocket error: {e}")
    finally:
        await hub.unregister(session.id)


if qi_config.dev_mode:
    qi_server.add_middleware(QiDevProxyMiddleware)
    log.debug("Dev mode enabled: using QiDevProxyMiddleware for routing.")
else:
    qi_server.add_middleware(QiSPAStaticFilesMiddleware)
