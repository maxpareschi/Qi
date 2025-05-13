import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from core.log import log

app = FastAPI()


async def dev_proxy(request: Request, call_next):
    """Middleware to log all incoming requests"""
    log.info(f"Request: {request.method} {request.url.path}")

    log.info(f"Dev servers: {os.getenv('QI_UI_DEV_SERVERS')}")

    if dev_servers := json.loads(os.getenv("QI_UI_DEV_SERVERS", "{}")):
        for addon_name, server_url in dev_servers.items():
            if request.url.path.startswith(f"/{addon_name}"):
                log.info(f"Redirecting to {server_url}{request.url.path}")
                response = RedirectResponse(url=f"{server_url}{request.url.path}")
                break
            else:
                log.info(f"No redirect for {request.url.path}")
                response = await call_next(request)
    else:
        response = await call_next(request)

    # Log the response status code
    log.info(
        f"Response: {request.method} {request.url.path} - Status: {response.status_code}"
    )

    return response


# Add a simple debug endpoint
@app.get("/debug")
async def debug_info():
    dev_mode = os.getenv("QI_DEV", "0")
    ui_dev_servers = "\n".join(
        [
            f"<li>{k}: {v}</li>"
            for k, v in json.loads(os.getenv("QI_UI_DEV_SERVERS", "{}")).items()
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

    # return {
    #     "dev_mode": os.getenv("QI_DEV") == "1",
    #     "ui_dev_servers": json.loads(os.getenv("QI_DEV_SERVERS", "{}")),
    # }


@app.get("/")
async def root():
    return {"message": "Fastapi is working."}


if os.getenv("QI_DEV") == "1":
    log.info("QI DEV MODE ON!")
    app.middleware("http")(dev_proxy)

app.mount("/static", StaticFiles(directory="static"), name="static")
