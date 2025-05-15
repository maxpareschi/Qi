import argparse
import json
import os
import subprocess
import threading
import time

import webview
from dotenv import load_dotenv

from core.log import log
from hub.utils import (
    WebViewControlApi,
    get_dev_servers,
    sanitize_env_vars,
    sanitize_server_address,
)

load_dotenv()

_stub_window: webview.Window | None = None
_windows: dict[str, webview.Window] = {}
_server_process: threading.Thread | None = None


def run_server(
    host: str,
    port: int,
    ssl_key_path: str | None = None,
    ssl_cert_path: str | None = None,
) -> subprocess.Popen:
    server_host = host.split("://")[1].split(":")[0]
    port = os.getenv("QI_LOCAL_PORT", "8000")

    cmd = [
        "uvicorn",
        "core.server:app",
        "--host",
        server_host,
        "--port",
        str(port),
    ]

    if os.getenv("QI_DEV") == "1":
        cmd.extend(["--log-level", "debug", "--workers", "1"])
    else:
        cmd.extend(["--log-level", "info", "--workers", "1"])

    if ssl_key_path and ssl_cert_path:
        cmd.extend(["--ssl-keyfile", ssl_key_path, "--ssl-certfile", ssl_cert_path])

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    if args.dev:
        log.debug("QI_DEV mode enabled.")
        os.environ["QI_DEV"] = "1"

    qi_dev_mode = bool(int(os.getenv("QI_DEV", "0")))
    qi_local_server = sanitize_server_address(
        os.getenv("QI_LOCAL_SERVER", "http://127.0.0.1")
    )
    qi_local_port = int(os.getenv("QI_LOCAL_PORT", "8000"))

    sanitize_env_vars(
        {
            "QI_LOCAL_SERVER": qi_local_server,
            "QI_LOCAL_PORT": qi_local_port,
            "QI_DEV": int(qi_dev_mode),
        }
    )

    addon_paths = os.listdir("addons")  # to be replaced with addon manager call
    addon_urls = dict()

    if qi_dev_mode:
        addon_urls = get_dev_servers(qi_local_server, target_servers=len(addon_paths))
    else:
        for addon_name in addon_paths:
            log.debug(f"Found addon: {addon_name}")
            addon_urls[addon_name] = f"{qi_local_server}:{qi_local_port}/{addon_name}"

    os.environ["QI_ADDONS"] = json.dumps(addon_urls)
    log.debug(f"QI_ADDONS: {addon_urls}")

    _server_process = run_server(qi_local_server, qi_local_port)

    # _stub_window = webview.create_window(
    #     "QiStub",
    #     html="<html><body></body></html>",
    #     hidden=True,
    #     focus=False,
    # )

    log.info(f"Starting {len(addon_urls)} addon windows")
    for addon_name, url in addon_urls.items():
        log.debug(f"Creating window for addon '{addon_name}' with URL: {url}")
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
            easy_drag=False,
            min_size=(350, 250),
        )

        log.debug(
            f"Activated webviews: {[win.title + ' | ' + url + ' | ' + win.uid for win in webview.windows]}"
        )

    webview.start(icon="../static/qi_512.png", debug=qi_dev_mode)

    _server_process.terminate()

    os._exit(0)
