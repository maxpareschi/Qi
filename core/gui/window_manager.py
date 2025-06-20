# core/gui/window_manager.py

"""
This module contains the manager for all Qi windows.
"""

import uuid
from functools import partial
from typing import Any, Final

import webview

from core.config import qi_launch_config
from core.gui import window_api
from core.logger import get_logger

log = get_logger(__name__)


class QiWindowManager:
    """A manager for windows that handles the creation, management,
    and destruction of windows. It's the main entry point for the
    GUI. The run method starts the main loop.
    """

    def __init__(self):
        self._windows: dict[str, webview.Window] = {}

    def _on_closed(self, window_id: str):
        log.debug(f"Window '{window_id}' closed by user, removing from registry.")
        if window_id in self._windows:
            del self._windows[window_id]

    def create_window(
        self,
        addon: str,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Create a new window for the given addon and session_id."""
        session_id = session_id or str(uuid.uuid4())
        window_id = str(uuid.uuid4())

        server_address = qi_launch_config.host
        server_port = qi_launch_config.port
        use_ssl = (
            qi_launch_config.ssl_key_path is not None
            and qi_launch_config.ssl_cert_path is not None
        )
        protocol = "https" if use_ssl else "http"
        url = f"{protocol}://{server_address}:{server_port}/{addon}?session_id={session_id}&window_id={window_id}"

        launch_kwargs: dict[str, Any] = {
            "min_size": (400, 300),
            "background_color": "#000000",
            "frameless": True,
            "easy_drag": False,
            "hidden": True,
            "js_api": None,
            **kwargs,
        }

        try:
            window = webview.create_window(url=url, title=addon, **launch_kwargs)

            # Expose API functions to the window's JS context
            window.expose(partial(window_api.close, window))
            window.expose(partial(window_api.minimize, window))
            window.expose(partial(window_api.maximize, window))
            window.expose(partial(window_api.restore, window))
            window.expose(partial(window_api.hide, window))
            window.expose(partial(window_api.show, window))
            window.expose(partial(window_api.move, window))
            window.expose(partial(window_api.resize, window))

            self._windows[window_id] = window

            # We only need to know when the user closes the window to clean up our registry
            window.events.closed += partial(self._on_closed, window_id)

            log.debug(f"Created window '{window_id}' for addon '{addon}'.")
            return window_id

        except Exception as e:
            log.error(f"Error creating window: {e}")
            return ""

    def list_windows(self) -> list[str]:
        """List active window IDs."""
        return list(self._windows.keys())

    def get_window(self, window_id: str) -> webview.Window | None:
        """Get a window instance by its window_id."""
        return self._windows.get(window_id)

    def close(self, window_id: str) -> str | None:
        """Close a specific window."""
        window = self.get_window(window_id)
        if window:
            window.destroy()
            return window_id
        return None

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Run the webview server and the event loop."""
        log.debug(f"Running webview.start with debug={qi_launch_config.dev_mode}.")
        webview.start(*args, debug=qi_launch_config.dev_mode, **kwargs)

    def exit(self) -> None:
        """Destroy all windows to end event loop."""
        log.debug("Destroying all windows to end event loop.")
        for window_id in list(self._windows.keys()):
            self.close(window_id)


qi_window_manager: Final[QiWindowManager] = QiWindowManager()
