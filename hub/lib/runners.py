import os
import subprocess
import threading
import time

from core.log import log, subprocess_logger


def run_server(
    host: str,
    port: int,
    ssl_key_path: str | None = None,
    ssl_cert_path: str | None = None,
    new_session: bool = False,
) -> subprocess.Popen:
    dev_mode = bool(int(os.getenv("QI_DEV_MODE", "0")))
    host = os.getenv("QI_LOCAL_SERVER", host)
    port = str(os.getenv("QI_LOCAL_PORT", port))

    if host.startswith("http"):
        raise ValueError("Host must specify only address without protocol.")
    if ":" in host:
        raise ValueError("Host must not contain a port")

    cmd = [
        "uvicorn",
        "core.server:app",
        "--host",
        host,
        "--port",
        port,
        "--workers",
        "1",
        "--log-level",
        "debug" if dev_mode else "info",
    ]

    if ssl_key_path and ssl_cert_path:
        cmd.extend(["--ssl-keyfile", ssl_key_path, "--ssl-certfile", ssl_cert_path])

    log.debug(f"Running server with command: {' '.join(cmd)}")

    server_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=os.environ,
        text=True,
        bufsize=1,
        start_new_session=new_session,
    )

    threading.Thread(
        target=subprocess_logger, args=(server_process,), daemon=True
    ).start()

    time.sleep(0.5)
    if server_process.poll():
        raise Exception("Server failed to start.")

    return server_process
