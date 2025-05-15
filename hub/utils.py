import logging
import os
import time

import httpx
import mouse
import webview
from webview.window import FixPoint

from core.log import log


class WebViewControlApi:
    def __init__(self):
        log.debug("WebViewControlApi initialized")

    def resize_window(self, direction: str):
        is_resizing = True

        log.debug(f"Starting window resize: {direction}")

        def stop_resizing():
            nonlocal is_resizing
            is_resizing = False

        button_event = mouse.on_button(
            buttons=mouse.LEFT,
            types=mouse.UP,
            callback=stop_resizing,
        )

        window = webview.active_window()
        if window is None or window.hidden:
            return {"message": "Window is not active"}

        original_width = window.width
        original_height = window.height
        drag_start_x, drag_start_y = mouse.get_position()

        while is_resizing:
            delta_x, delta_y = mouse.get_position()

            delta_x -= drag_start_x
            delta_y -= drag_start_y

            computed_width = original_width
            computed_height = original_height

            origin = FixPoint.NORTH | FixPoint.WEST

            if direction == "left":
                computed_width = original_width - delta_x
                origin = FixPoint.EAST
            elif direction == "top":
                computed_height = original_height - delta_y
                origin = FixPoint.SOUTH
            elif direction == "right":
                computed_width = original_width + delta_x
            elif direction == "bottom":
                computed_height = original_height + delta_y
                origin = FixPoint.NORTH
            elif direction == "handle":
                computed_width = original_width + delta_x
                computed_height = original_height + delta_y

            if computed_width < window.min_size[0]:
                computed_width = window.min_size[0]

            if computed_height < window.min_size[1]:
                computed_height = window.min_size[1]

            window.resize(
                computed_width,
                computed_height,
                fix_point=origin,
            )
            time.sleep(0.01)

        is_resizing = False
        mouse._listener.remove_handler(button_event)
        log.debug(f"Stopped window resize: {direction}")

    def close_window(self):
        window = webview.active_window()
        window.destroy()
        log.debug("Window closed")

    def minimize_window(self):
        window = webview.active_window()
        window.minimize()
        log.debug("Window minimized")

    def maximize_window(self):
        window = webview.active_window()
        if window.maximized:
            window.restore()
            window.maximized = False
            log.debug("Window restored")
        else:
            window.maximize()
            window.maximized = True
            log.debug("Window maximized")


def sanitize_server_address(server: str) -> str:
    protocol = "http"
    server_base_path = "127.0.0.1"
    if server.startswith("https://"):
        protocol = "https"
    if server.startswith("file://"):
        protocol = "file"
    try:
        server_base_path = server.split("://")[1].rstrip("/")
    except IndexError:
        server_base_path = server.rstrip("/")
    return f"{protocol}://{server_base_path}"


def sanitize_env_vars(env_vars: dict[str, str]):
    for key, value in env_vars.items():
        os.environ[key] = str(value)


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
            url = f"{server}:{port}/vite"
            try:
                addon_name = client.get(url, timeout=0.01).headers.get(
                    "X-Qi-Addon", None
                )
                if addon_name:
                    discovered_servers[addon_name] = f"{server}:{port}/{addon_name}"
            except httpx.RequestError:
                continue

        if len(discovered_servers.keys()) >= target_servers:
            break

        log.warning(f"No dev servers found on {server}:{port_range} retrying...")
        time.sleep(0.01)

    log.setLevel(original_log_level)

    log.info(f"Found {len(discovered_servers)} dev servers: {discovered_servers}")
    client.close()

    return discovered_servers
