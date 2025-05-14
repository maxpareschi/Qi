import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from core.log import log

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


# Add a simple debug endpoint
@app.get("/debug")
async def debug_info():
    log.debug(json.loads(os.getenv("QI_DEV_VITE_SERVERS", "{}")))
    dev_mode = os.getenv("QI_DEV", "0")
    ui_dev_servers = "\n".join(
        [
            f"<li>{k}: {v}</li>"
            for k, v in json.loads(os.getenv("QI_DEV_VITE_SERVERS", "{}")).items()
        ]
    )
    return HTMLResponse(
        content=f"""
        <html>
            <head>
                <title>Qi Debug</title>
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                    }}
                    html {{
                        font-size: 13px;
                    }}
                    body {{
                        font-family: \"Microsoft Sans Serif\", \"FiraCode Nerd Font Light\", monospace;
                        background-color: #151515;
                        color: #bbb;
                    }}
                    img {{
                        width: 10rem;
                        height: 10rem;
                        padding: 2rem;
                    }}
                    li {{
                        margin-left: 2rem;
                        margin-top: 0.5rem;
                    }}
                    .debug-sidebar, .debug-info, .debug-card {{
                        height: 100%;
                    }}
                    .debug-card {{
                        display: flex;
                        flex-direction: row;
                        align-items: center;
                    }}
                    .debug-sidebar {{
                        background-color: #222;
                    }}
                    .debug-text {{
                        display: flex;
                        flex-direction: column;
                        gap: 0.7rem;
                        padding: 2rem;
                    }}
                    .separator {{
                        height: 1px;
                        background-color: #222;
                        width: 100%;
                    }}
                </style>
            </head>
            <body>
                <div class="debug-card">
                    <div class="debug-sidebar">
                        <img src="/static/qi_512.png" alt="Qi Logo" />
                    </div>
                    <div class="debug-info">
                        <div class="debug-text">
                        <h1>Qi Debug Info</h1>
                        <div class="separator"></div>
                        <p>Dev mode: {dev_mode}</p>
                        <div class="separator"></div>
                        <div>Dev servers:
                            <ul>
                                {ui_dev_servers}
                            </ul>
                        </div>
                        <div class="separator"></div>
                    </div>
                </div>
            </body>
        </html>"""
    )


@app.get("/")
async def root():
    return {"message": "Fastapi is working."}


async def dev_proxy(request: Request, call_next):
    """Middleware to log all incoming requests"""
    print(f"[PRINT] Request: {request.method} {request.url.path}", flush=True)

    print(f"[PRINT] Dev servers: {os.getenv('QI_DEV_VITE_SERVERS')}", flush=True)

    if dev_servers := json.loads(os.getenv("QI_DEV_VITE_SERVERS", "{}")):
        for addon_name, server_url in dev_servers.items():
            if request.url.path.startswith(f"/{addon_name}"):
                print(
                    f"[PRINT] Redirecting to {server_url}{request.url.path}", flush=True
                )
                response = RedirectResponse(url=f"{server_url}{request.url.path}")
                break
            else:
                print(f"[PRINT] No redirect for {request.url.path}", flush=True)
                response = await call_next(request)
    else:
        response = await call_next(request)

    print(
        f"[PRINT] Response: {request.method} {request.url.path} - Status: {response.status_code}",
        flush=True,
    )

    return response


# Diagnostic print for QI_DEV in core/server.py module scope
actual_qi_dev_value = os.getenv("QI_DEV")
print(
    f"[CORE_SERVER_MODULE] QI_DEV as seen by core/server.py: '{actual_qi_dev_value}' (type: {type(actual_qi_dev_value)})",
    flush=True,
)

# Diagnostic print for QI_DEV_VITE_SERVERS
actual_vite_servers_value = os.getenv("QI_DEV_VITE_SERVERS")
print(
    f"[CORE_SERVER_MODULE] QI_DEV_VITE_SERVERS as seen by core/server.py: '{actual_vite_servers_value}' (type: {type(actual_vite_servers_value)})",
    flush=True,
)

if actual_qi_dev_value == "1":
    print("[PRINT] QI DEV MODE ON! (Middleware SHOULD be applied)", flush=True)
    app.middleware("http")(dev_proxy)
else:
    print(
        f"[PRINT] QI DEV MODE OFF! (Middleware will NOT be applied based on QI_DEV='{actual_qi_dev_value}')",
        flush=True,
    )
