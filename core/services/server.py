import json
import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from core.services.connection_manager import connection_manager, websocket_endpoint
from core.services.log import log

# Debug: Check connection manager object ID
log.info(f"Server.py: Connection manager instance ID: {id(connection_manager)}")
log.info("Server.py: Beginning handler registration")
connection_manager.subscribe("debug.server")(
    _debug_server_handler := lambda t, p, s: log.info(
        f"SERVER DEBUG HANDLER: {t}, {p}, {s}"
    )
)
log.info("Registered debug.server handler")
connection_manager.list_handlers()


async def dev_proxy(request: Request, call_next):
    """Middleware to log all incoming requests"""

    if dev_servers := json.loads(os.getenv("QI_ADDONS", "{}")):
        for addon_name, server_url in dev_servers.items():
            log.debug(
                f'Name: "{addon_name}", URL: "{server_url}", REQUEST: "{request.url.path}"'
            )
            if request.url.path.startswith(f"/{addon_name}"):
                response = RedirectResponse(url=f"{server_url}/{addon_name}")
                break
            else:
                response = await call_next(request)
    else:
        response = await call_next(request)

    return response


qi_server = FastAPI()
qi_server.websocket("/ws")(websocket_endpoint)

if bool(int(os.getenv("QI_DEV_MODE", "0"))):
    qi_server.middleware("http")(dev_proxy)
    log.info("DevProxyMiddleware enabled")

else:
    for addon_name in os.listdir("addons"):
        qi_server.mount(
            f"/{addon_name}",
            StaticFiles(directory=f"addons/{addon_name}/ui", html=True),
            name=addon_name,
        )

qi_server.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.getcwd(), "static")),
    name="static",
)


@qi_server.get("/")
async def root():
    return {"message": "Qi Fastapi local server is running."}
