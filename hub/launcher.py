import argparse
import json
import os
import subprocess
import threading
import time

import httpx
import webview

from core.log import log

_stub_window: webview.Window | None = None
_windows: dict[str, webview.Window] = {}
_server_process: threading.Thread | None = None


def get_dev_vite_servers():
    _dev_vite_server_cache: dict[str, str] = {}
    client = httpx.Client()
    time.sleep(0.5)
    for port in range(5173, 5200):
        try:
            # log.debug(f"Trying to connect to Vite server at port {port}")
            # log.setLevel(20)
            addon_name = client.get(
                f"http://127.0.0.1:{port}/healthcheck", timeout=0.03
            ).headers.get("X-Qi-Addon", None)
            # log.setLevel(10)
            if addon_name:
                _dev_vite_server_cache[addon_name] = f"http://127.0.0.1:{port}"
        except httpx.RequestError as e:
            log.debug(f"No Vite server at port {port}: {str(e)}")
            continue
    log.info(
        f"Found {len(_dev_vite_server_cache)} dev servers: {_dev_vite_server_cache}"
    )
    client.close()
    os.environ["QI_DEV_VITE_SERVERS"] = json.dumps(_dev_vite_server_cache)


def run_server():
    log.debug("Starting server...")

    subprocess_env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "QI_DEV": str(os.environ.get("QI_DEV", "0")),
        "QI_LOCAL_SERVER": os.getenv("QI_LOCAL_SERVER", "127.0.0.1"),
        "QI_LOCAL_PORT": str(os.getenv("QI_LOCAL_PORT", "8000")),
        "QI_DEV_VITE_SERVERS": str(os.getenv("QI_DEV_VITE_SERVERS", {})),
    }

    cmd = [
        "uvicorn",
        "core.server:app",
        "--host",
        os.getenv("QI_LOCAL_SERVER", "127.0.0.1"),
        "--port",
        os.getenv("QI_LOCAL_PORT", "8000"),
    ]

    if os.getenv("QI_DEV") == "1":
        cmd.extend(["--log-level", "debug", "--workers", "1"])
    else:
        cmd.extend(["--log-level", "info", "--workers", "4"])

    server_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=subprocess_env,
        text=True,
        bufsize=1,
    )

    def console_relay_logs(process):
        while process.poll() is None:
            nextline = process.stdout.readline()
            if nextline.find(" | ") >= 0:
                nextline = nextline.split(" | ")[2].strip()
            if nextline.strip() == "":
                continue
            level = nextline.split(":")[0].strip()
            message = ":".join(nextline.split(":")[1:]).strip()
            if message.find("|") >= 0:
                message = message.split(" | ")[2].strip()
            if level.find("DEBUG") >= 0:
                log.debug(message)
            elif level.find("INFO") >= 0:
                log.info(message)
            elif level.find("WARNING") >= 0:
                log.warning(message)
            elif level.find("ERROR") >= 0:
                log.error(message)
            elif level.find("CRITICAL") >= 0:
                log.critical(message)
            else:
                log.debug(nextline.strip())

    threading.Thread(
        target=console_relay_logs, args=(server_process,), daemon=True
    ).start()

    # time.sleep(0.5)
    return server_process


if __name__ == "__main__":
    for handler in webview.logger.handlers:
        webview.logger.removeHandler(handler)
    webview.logger.addHandler(log.handlers[0])

    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    os.environ["QI_DEV"] = "1" if args.dev else "0"

    os.environ["QI_LOCAL_SERVER"] = os.getenv("QI_LOCAL_SERVER", "127.0.0.1")
    os.environ["QI_LOCAL_PORT"] = os.getenv("QI_LOCAL_PORT", "8000")

    if os.getenv("QI_DEV") == "1":
        get_dev_vite_servers()

    _server_process = run_server()

    _stub_window = webview.create_window(
        "QiStub",
        html="<html><body></body></html>",
        hidden=True,
    )

    for addon_name, url in json.loads(os.getenv("QI_DEV_VITE_SERVERS", "{}")).items():
        _windows[addon_name] = webview.create_window(
            addon_name,
            url=url,
            frameless=True,
            easy_drag=False,
            width=800,
            height=600,
            x=500,
            y=300,
        )

    webview.start()
