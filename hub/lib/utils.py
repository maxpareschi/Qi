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


def get_addons(
    max_tries: int = 10,
) -> dict[str, str]:
    """
    Get all addons from the server.
    """
    server: str = os.getenv("QI_LOCAL_SERVER")
    port: int = int(os.getenv("QI_LOCAL_PORT"))
    dev: bool = os.getenv("QI_DEV_MODE") == "1"
    addon_paths = [
        path.strip().replace("\\", "/")
        for path in os.getenv("QI_ADDON_PATHS").split(os.pathsep)
    ]
    port_range: tuple[int, int] = (5173, 5200)
    client = httpx.Client()
    discovered_addons: dict[str, str] = dict()

    original_log_level = log.getEffectiveLevel()
    logger.set_level(logger.WARNING)

    if not dev:
        for addon_path in addon_paths:
            for addon_name in os.listdir(addon_path):
                addon_path = os.path.join(addon_path, addon_name)
                if os.path.isdir(addon_path) and os.path.exists(
                    os.path.join(addon_path, "addon.py")
                ):
                    discovered_addons[addon_name] = {
                        "url": f"http://{server}:{port}",
                        "path": os.path.abspath(
                            os.path.join(addon_path, addon_name)
                        ).replace("\\", "/"),
                    }
    else:
        for _ in range(max_tries):
            discovered_addons = {}

            for port in range(*port_range):
                url = f"http://{server}:{port}/vite"
                try:
                    addon_name = client.get(url, timeout=0.01).headers.get(
                        "X-Qi-Addon", None
                    )
                    if addon_name:
                        discovered_addons[addon_name] = {
                            "url": f"http://{server}:{port}",
                            "path": os.path.abspath(
                                os.path.join("addons", addon_name)
                            ).replace("\\", "/"),
                        }
                except httpx.RequestError:
                    continue

            if len(discovered_addons.keys()) >= len(addon_paths):
                break

            log.warning(f"No dev servers found on {server}:{port_range} retrying...")
            time.sleep(0.01)

        client.close()

    logger.set_level(original_log_level)
    log.info(f"Discovered addons: {discovered_addons}")

    return discovered_addons
