import json
import logging
import os
import time

import httpx

from core.log import log


def set_dev_mode(mode: bool | None) -> bool:
    os.environ["QI_DEV_MODE"] = "1" if mode else "0"
    return get_dev_mode()


def get_dev_mode() -> bool:
    return bool(int(os.getenv("QI_DEV_MODE", "0")))


def sanitize_server_address(server: str) -> str:
    server = server.removeprefix("http://").removeprefix("https://")
    if ":" in server:
        server = server.split(":")[0]
    return server


def update_env(
    **kwargs: int | bool | str | float | dict[str, str | int | bool | float],
):
    """
    Update the environment variables with the given arguments.

    Args:
        **kwargs: int | bool | str | float | dict[str, str | int | bool | float]
    """
    for key, value in kwargs.items():
        if isinstance(value, dict):
            value = json.dumps(value)
        os.environ[key.upper()] = str(value)


def get_dev_servers(
    server: str,
    target_servers: int = 1,
    max_tries: int = 10,
    port_range: tuple[int, int] = (5173, 5200),
) -> dict[str, str]:
    client = httpx.Client()
    discovered_servers: dict[str, str] = dict()

    original_log_level = log.getEffectiveLevel()
    log.setLevel(logging.WARNING)

    for _ in range(max_tries):
        discovered_servers = {}

        for port in range(*port_range):
            url = f"http://{server}:{port}/vite"
            try:
                addon_name = client.get(url, timeout=0.01).headers.get(
                    "X-Qi-Addon", None
                )
                if addon_name:
                    discovered_servers[addon_name] = (
                        f"http://{server}:{port}/{addon_name}"
                    )
            except httpx.RequestError:
                continue

        if len(discovered_servers.keys()) >= target_servers:
            break

        log.warning(f"No dev servers found on {server}:{port_range} retrying...")
        time.sleep(0.01)

    log.setLevel(original_log_level)
    client.close()

    return discovered_servers
