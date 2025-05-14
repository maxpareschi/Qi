import argparse
import json
import os
import subprocess
import sys
import threading
import time

import httpx
import webview

from core.log import log

_stub_window: webview.Window | None = None
_server_thread: threading.Thread | None = None


def get_dev_vite_servers():
    _dev_vite_server_cache: dict[str, str] = {}
    client = httpx.Client()
    for port in range(5173, 5190):
        try:
            # log.debug(f"Trying to connect to Vite server at port {port}")
            # log.setLevel(20)
            addon_name = client.get(
                f"http://127.0.0.1:{port}/healthcheck", timeout=0.01
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

    root_dir = os.getcwd()
    scripts_dir = os.path.join(root_dir, "Scripts")
    site_packages_dir = os.path.join(root_dir, "lib", "site-packages")
    subprocess_env = {
        "PYTHONPATH": (
            root_dir + os.pathsep + site_packages_dir + os.pathsep + scripts_dir
        ).replace("\\", "/"),
        "PYTHONUNBUFFERED": "1",
        "QI_DEV": str(os.environ.get("QI_DEV", "0")),
        "QI_LOCAL_SERVER": os.getenv("QI_LOCAL_SERVER", "127.0.0.1"),
        "QI_LOCAL_PORT": str(os.getenv("QI_LOCAL_PORT", "8000")),
        "QI_DEV_VITE_SERVERS": str(os.getenv("QI_DEV_VITE_SERVERS", {})),
    }

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "core.server:app",
        "--host",
        os.getenv("QI_LOCAL_SERVER", "127.0.0.1"),
        "--port",
        os.getenv("QI_LOCAL_PORT", "8000"),
    ]

    if os.getenv("QI_DEV") == "1":
        cmd.extend(
            [
                "--reload",
                "--log-level",
                "debug",
            ]
        )
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

    def _relay(process):
        while process.poll() is None:
            nextline = process.stdout.readline()
            print(nextline)
            if nextline == "":
                continue
            level = nextline.split(":")[0]
            message = ":".join(nextline.split(":")[1:])
            if level == "DEBUG":
                log.debug(message)
            elif level == "INFO":
                log.info(message)
            elif level == "WARNING":
                log.warning(message)
            elif level == "ERROR":
                log.error(message)
            elif level == "CRITICAL":
                log.critical(message)
            else:
                log.error(nextline)

    threading.Thread(target=_relay, args=(server_process,), daemon=True).start()

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

    os.environ["QI_LOCAL_SERVER"] = "127.0.0.1"
    os.environ["QI_LOCAL_PORT"] = "8000"

    if os.getenv("QI_DEV") == "1":
        get_dev_vite_servers()

    server_process = run_server()

    while True:
        time.sleep(1)
