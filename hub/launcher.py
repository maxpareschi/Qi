import argparse
import json
import os
import subprocess
import threading
import time

import webview
from dotenv import load_dotenv

from core.log import log
from hub.utils import WebViewControlApi, get_dev_servers

load_dotenv()

_stub_window: webview.Window | None = None
_windows: dict[str, webview.Window] = {}
_server_process: threading.Thread | None = None


def run_server():
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
        env=os.environ,
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
    qi_dev_mode = bool(int(os.getenv("QI_DEV", "0")))
    qi_local_server = os.getenv("QI_LOCAL_SERVER", "http://127.0.0.1")
    qi_local_port = os.getenv("QI_LOCAL_PORT", "8000")

    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    if args.dev:
        log.debug("QI_DEV mode enabled.")
        qi_dev_mode = True
        os.environ["QI_DEV"] = "1"

    if qi_dev_mode:
        addon_urls = get_dev_servers(qi_local_server)
    else:
        addon_urls = dict()
        for addon_name in os.listdir("addons"):
            log.debug(f"Found addon: {addon_name}")
            addon_urls[addon_name] = f"{qi_local_server}:{qi_local_port}/{addon_name}"

    os.environ["QI_ADDONS"] = json.dumps(addon_urls)

    log.debug(f"QI_ADDONS: {addon_urls}")

    _server_process = run_server()

    # _stub_window = webview.create_window(
    #     "QiStub",
    #     html="<html><body></body></html>",
    #     hidden=True,
    #     focus=False,
    # )

    for addon_name, url in addon_urls.items():
        _windows[addon_name] = webview.create_window(
            addon_name,
            url=url,
            frameless=True,
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
        log.debug(
            f"Activated webviews: {[win.title + ' | ' + str(win.original_url) + ' | ' + win.uid for win in webview.windows]}"
        )
        webview.start(debug=qi_dev_mode)
