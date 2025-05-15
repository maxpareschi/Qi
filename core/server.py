import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from core.log import log

app = FastAPI()

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

# app.mount(
#     "/static",
#     StaticFiles(directory=static_dir),
#     name="static",
# )

# log.debug(f"Static directory: {static_dir}")


# Add a simple debug endpoint
@app.get("/debug")
async def debug_info():
    dev_mode = os.getenv("QI_DEV_MODE", "0")
    dev_vite_servers = json.loads(os.getenv("QI_ADDONS", "{}"))
    log.debug(f"Debug Page: QI_DEV_MODE: {dev_mode}, QI_ADDONS: {dev_vite_servers}")
    ui_dev_servers = "\n".join(
        [f"<li>{k}: {v}</li>" for k, v in dev_vite_servers.items()]
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
                        <div>Addon urls:
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
    if dev_servers := json.loads(os.getenv("QI_ADDONS", "{}")):
        for addon_name, server_url in dev_servers.items():
            if request.url.path.startswith(f"/{addon_name}"):
                response = RedirectResponse(url=f"{server_url}{request.url.path}")
                break
            else:
                response = await call_next(request)
    else:
        response = await call_next(request)

    return response


if bool(int(os.getenv("QI_DEV_MODE", "0"))):
    app.middleware("http")(dev_proxy)
else:
    for addon_name in os.listdir("addons"):
        app.mount(
            f"/{addon_name}",
            StaticFiles(directory=f"addons/{addon_name}/ui", html=True),
            name=addon_name,
        )
