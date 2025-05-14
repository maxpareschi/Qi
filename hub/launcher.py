import argparse
import json
import os
import subprocess
import threading
import time

import httpx
import mouse
import webview
from webview.window import FixPoint

from core.log import log

_stub_window: webview.Window | None = None
_windows: dict[str, webview.Window] = {}
_server_process: threading.Thread | None = None


class WebViewControlApi:
    def __init__(self):
        self.is_resizing = False
        pass

    def start_resize(self):
        window = webview.active_window()
        if window is None or window.hidden:
            return {"message": "Window is not active"}

        original_width = window.width
        original_height = window.height
        drag_start_x = mouse.get_position()[0]
        drag_start_y = mouse.get_position()[1]

        self.is_resizing = True

        while self.is_resizing:
            delta_x = mouse.get_position()[0] - drag_start_x
            delta_y = mouse.get_position()[1] - drag_start_y
            window.resize(
                original_width + delta_x,
                original_height + delta_y,
                fix_point=FixPoint.NORTH | FixPoint.WEST,
            )
            time.sleep(0.01)

    def stop_resize(self):
        self.is_resizing = False

    def close_window(self):
        window = webview.active_window()
        window.destroy()

    def minimize_window(self):
        window = webview.active_window()
        window.minimize()

    def maximize_window(self):
        window = webview.active_window()
        if window.maximized:
            window.restore()
            window.maximized = False
        else:
            window.maximize()
            window.maximized = True


def get_dev_vite_servers():
    _dev_vite_server_cache: dict[str, str] = {}
    client = httpx.Client()
    time.sleep(0.5)
    for port in range(5173, 5200):
        try:
            addon_name = client.get(
                f"http://127.0.0.1:{port}/healthcheck", timeout=0.03
            ).headers.get("X-Qi-Addon", None)
            if addon_name:
                _dev_vite_server_cache[addon_name] = f"http://127.0.0.1:{port}"
        except httpx.RequestError:
            # log.debug(f"No Vite server at port {port}: {str(e)}")
            continue
    log.info(
        f"Found {len(_dev_vite_server_cache)} dev servers: {_dev_vite_server_cache}"
    )
    client.close()
    os.environ["QI_DEV_VITE_SERVERS"] = json.dumps(_dev_vite_server_cache)


def run_server():
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

    time.sleep(0.5)
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
        focus=False,
    )

    for addon_name, url in json.loads(os.getenv("QI_DEV_VITE_SERVERS", "{}")).items():
        _windows[addon_name] = webview.create_window(
            addon_name,
            url=url,
            frameless=True,
            # easy_drag=False,
            width=800,
            height=600,
            x=500,
            y=300,
            js_api=WebViewControlApi(),
            background_color="#222222",
            focus=True,
            text_select=False,
            min_size=(350, 250),
        )

    log.debug(f"Webviews active: {webview.windows}")

    webview.start()
