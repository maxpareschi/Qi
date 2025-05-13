import argparse
import json
import os
import threading
import time

import httpx
import uvicorn
import webview

from core.log import log

_stub_window: webview.Window | None = None
_server_thread: threading.Thread | None = None


def get_ui_dev_servers():
    _dev_server_cache: dict[str, str] = {}
    client = httpx.Client()
    for port in range(5173, 5190):
        try:
            # log.debug(f"Trying to connect to Vite server at port {port}")
            log.setLevel(20)
            addon_name = client.get(
                f"http://127.0.0.1:{port}/healthcheck", timeout=0.01
            ).headers.get("X-Qi-Addon", None)
            log.setLevel(10)
            if addon_name:
                _dev_server_cache[addon_name] = f"http://127.0.0.1:{port}"
        except httpx.RequestError as e:
            log.debug(f"No Vite server at port {port}: {str(e)}")
            continue
    log.info(f"Found {len(_dev_server_cache)} dev servers: {_dev_server_cache}")
    client.close()
    os.environ["QI_UI_DEV_SERVERS"] = json.dumps(_dev_server_cache)


def run_server():
    log.debug("Starting server...")
    uvicorn.run(
        "core.server:app",
        host=os.getenv("QI_LOCAL_HOST", "127.0.0.1"),
        port=int(os.getenv("QI_LOCAL_PORT", 8000)),
        log_level="debug",
        log_config=None,
    )


if __name__ == "__main__":
    for handler in webview.logger.handlers:
        webview.logger.removeHandler(handler)
    webview.logger.addHandler(log.handlers[0])

    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    os.environ["QI_DEV"] = "1" if args.dev else "0"

    os.environ["QI_LOCAL_HOST"] = "127.0.0.1"
    os.environ["QI_LOCAL_PORT"] = "8000"

    if os.getenv("QI_DEV") == "1":
        get_ui_dev_servers()

    _server_thread = threading.Thread(target=run_server, daemon=True)
    _server_thread.start()

    while True:
        time.sleep(1)
