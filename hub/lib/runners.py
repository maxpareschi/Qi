import os
import threading

import uvicorn


def run_server(
    host: str,
    port: int,
    ssl_key_path: str | None = None,
    ssl_cert_path: str | None = None,
    dev_mode: bool = True,
) -> threading.Thread:
    host = os.getenv("QI_LOCAL_SERVER", host)
    port = int(os.getenv("QI_LOCAL_PORT", port))

    if host.startswith("http"):
        raise ValueError("Host must specify only address without protocol.")
    if ":" in host:
        raise ValueError("Host must not contain a port")

    server_thread = threading.Thread(
        target=uvicorn.run,
        args=("core.server.server:qi_server",),
        kwargs={
            "host": host,
            "port": port,
            "log_level": "debug" if dev_mode else "info",
            "ssl_keyfile": ssl_key_path,
            "ssl_certfile": ssl_cert_path,
            "workers": 1,
            "log_config": None,
        },
        daemon=True,
    ).start()

    return server_thread
