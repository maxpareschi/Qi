import json
import os
import time

import httpx

from core import logger

log = logger.get_logger(__name__)


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
    logger.set_level(logger.WARNING)

    for _ in range(max_tries):
        discovered_servers = {}

        for port in range(*port_range):
            url = f"http://{server}:{port}/vite"
            try:
                addon_name = client.get(url, timeout=0.01).headers.get(
                    "X-Qi-Addon", None
                )
                if addon_name:
                    discovered_servers[addon_name] = f"http://{server}:{port}"
            except httpx.RequestError:
                continue

        if len(discovered_servers.keys()) >= target_servers:
            break

        log.warning(f"No dev servers found on {server}:{port_range} retrying...")
        time.sleep(0.01)

    client.close()

    logger.set_level(original_log_level)
    log.info(f"Discovered dev servers: {discovered_servers}")

    return discovered_servers
