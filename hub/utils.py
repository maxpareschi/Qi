import time

import httpx
import mouse
import webview
from webview.window import FixPoint

from core.log import log


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


def get_dev_servers(server: str) -> dict[str, str]:
    discovered_servers: dict[str, str] = {}
    client = httpx.Client()
    for port in range(5173, 5200):
        try:
            addon_name = client.get(f"{server}:{port}/vite", timeout=0.02).headers.get(
                "X-Qi-Addon", None
            )
            if addon_name:
                discovered_servers[addon_name] = f"{server}:{port}"
        except httpx.RequestError as e:
            log.debug(f"No Vite server at port {port}: {str(e)}")
            continue
    log.info(f"Found {len(discovered_servers)} dev servers: {discovered_servers}")
    client.close()
    return discovered_servers
