# main.py
import json
import os

from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from core.logging import get_logger
from core.server.bus import qi_bus

log = get_logger(__name__)
qi_dev_mode = os.getenv("QI_DEV_MODE", "0") == "1"


async def dev_proxy(request: Request, call_next):
    """Middleware to log all incoming requests"""

    if dev_servers := json.loads(os.getenv("QI_ADDONS", "{}")):
        for addon_name, server_url in dev_servers.items():
            log.debug(
                f'Name: "{addon_name}", URL: "{server_url}", REQUEST: "{request.url.path}", PARAMS: "{request.query_params}"'
            )
            if request.url.path.startswith(f"/{addon_name}"):
                response = RedirectResponse(
                    url=f"{server_url}/{addon_name}?{request.query_params}"
                )
                break
            else:
                response = await call_next(request)
    else:
        response = await call_next(request)

    return response


qi_server = FastAPI()


@qi_server.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await qi_bus.accept(ws, session_id)


if qi_dev_mode:
    qi_server.middleware("http")(dev_proxy)
    log.info("DevProxyMiddleware enabled")

else:
    for addon_name in os.listdir("addons"):
        qi_server.mount(
            f"/{addon_name}",
            StaticFiles(directory=f"addons/{addon_name}/ui", html=True),
            name=addon_name,
        )

# qi_server.mount(
#     "/static",
#     StaticFiles(directory=os.path.join(os.getcwd(), "static")),
#     name="static",
# )


@qi_server.get("/")
async def root():
    return {"message": "Qi Fastapi local server is running."}
