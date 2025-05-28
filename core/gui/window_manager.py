import os
import uuid
from typing import Any

import webview

from core import logger

log = logger.get_logger(__name__)


class _QiWindowManagerSingleton(type):
    _inst: "QiWindowManager|None" = None

    def __call__(cls, *a, **kw):
        if cls._inst is None:
            cls._inst = super().__call__(*a, **kw)
        return cls._inst

    def reset(cls):
        """Reset singleton for testing."""
        cls._inst = None


class QiWindowManager(metaclass=_QiWindowManagerSingleton):
    """A manager for windows that handles the creation, management,
    and destruction of windows. It's the main entry point for the
    GUI. The run method starts the main loop.
    """

    def __init__(self):
        self._windows: dict[str, webview.Window] = {}
        self.dev_mode = os.getenv("QI_DEV_MODE", "0") == "1"

    def create_window(
        self,
        addon: str,
        session_id: str = None,
        **kwargs: Any,
    ) -> str:
        """
        Create a new window for the given addon and session_id.

        Args:
            addon: The addon name (e.g., "addon-skeleton")
            session_id: The session identifier
            **kwargs: Additional window creation arguments

        Returns:
            The window_id (UUID string) of the created window
        """

        # build a single session_id if not provided by any requestor
        if not session_id:
            session_id = str(uuid.uuid4())

        window_id = str(uuid.uuid4())

        # this is a mandatory override on parameters, should not be changed or removed.

        server_address = os.getenv("QI_LOCAL_SERVER", "127.0.0.1")
        server_port = os.getenv("QI_LOCAL_PORT", 8000)
        server_protocol = (
            "http://"
            if (
                os.getenv("QI_SSL_KEY_PATH", None) is None
                or os.getenv("QI_SSL_CERT_PATH", None) is None
            )
            else "https://"
        )

        url = f"{server_protocol}{server_address}:{server_port}/{addon}?session_id={session_id}&window_id={window_id}"

        launch_kwargs: dict[str, Any] = kwargs
        launch_kwargs.update(
            {
                "min_size": (400, 300),
                "background_color": "#000000",
                "frameless": True,
                "easy_drag": False,
                "js_api": None,
                "hidden": True,
            }
        )

        try:
            # Create the window instance
            window = webview.create_window(
                url=url,
                title=f"{addon}",
                **launch_kwargs,
            )

            # Set our custom attributes on the window instance
            window.__setattr__("addon", addon)
            window.__setattr__("session_id", session_id)
            window.__setattr__("window_id", window_id)

            # Store in registry
            self._windows[window_id] = window
            log.debug(
                f"Created window '{window_id}' for session '{session_id}' by addon '{addon}'."
            )
            window.events.loaded += window.show
            return window_id

        except Exception as e:
            log.error(f"Error creating window: {e}")
            return None

    def list_windows(
        self, session_id: str | None = None, addon: str | None = None
    ) -> list[dict]:
        """
        List all active windows.
        """
        lookup_keys = {}
        if session_id is not None:
            lookup_keys["session_id"] = session_id
        if addon is not None:
            lookup_keys["addon"] = addon

        result = []

        for window_id, window in self._windows.items():
            if (
                all(getattr(window, key) == value for key, value in lookup_keys.items())
                or all(
                    window.__getattribute__(key) is None for key in lookup_keys.keys()
                )
                or all(window.__dict__.get(key) is None for key in lookup_keys.keys())
                or not lookup_keys
            ):
                result.append(
                    {
                        "addon": window.addon,
                        "session_id": window.session_id,
                        "window_id": window_id,
                    }
                )

        return result

    def list_all(self) -> list[dict]:
        """
        List all active windows.

        Returns:
            List of window information dictionaries
        """
        return [
            {
                "addon": window.addon,
                "session_id": window.session_id,
                "window_id": window_id,
            }
            for window_id, window in self._windows.items()
        ]

    def list_by_session_id(self, session_id: str) -> list[dict]:
        """
        List all windows for a specific session_id.

        Args:
            session_id: The session identifier to filter by

        Returns:
            List of window information dictionaries
        """
        return [
            {
                "addon": window.addon,
                "session_id": window.session_id,
                "window_id": window_id,
            }
            for window_id, window in self._windows.items()
            if window.session_id == session_id
        ]

    def list_by_addon(self, addon: str) -> list[dict]:
        """
        List all windows for a specific addon.
        """
        return [
            {
                "addon": window.addon,
                "session_id": window.session_id,
                "window_id": window_id,
            }
            for window_id, window in self._windows.items()
            if window.addon == addon
        ]

    def get_window(self, window_id: str) -> webview.Window | None:
        """
        Get a window instance by its window_id.

        Args:
            window_id: The window identifier

        Returns:
            The window instance, or None if not found
        """
        window = self._windows.get(window_id)
        log.debug(f"Window '{window_id}' found.") if window else log.warning(
            f"Window '{window_id}' not found."
        )
        return window

    def invoke(self, window_id: str, method: str, *args, **kwargs) -> Any | None:
        """
        Invoke a method on a specific window.

        Args:
            window_id: The window identifier
            method: The method name to invoke
            *args: Arguments to pass to the method

        Returns:
            The result of the method call, or None if window not found
        """
        window = self.get_window(window_id)
        if window and hasattr(window, method):
            log.debug(f"Running method '{method}' on window '{window_id}'.")
            return getattr(window, method)(*args, **kwargs)
        else:
            log.warning(f"Invoking method '{method}' failed.")
            return None

    def close(self, window_id: str) -> str | None:
        """
        Close a specific window.

        Args:
            window_id: The window identifier to close

        Returns:
            The window_id if successfully closed, None otherwise
        """
        window = self.get_window(window_id)
        if window:
            window.destroy()
            del self._windows[window_id]
            log.debug(f"Window '{window_id}' closed.")
            return window_id

        log.warning(f"Closing window '{window_id}' failed: Window not found.")
        return None

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Run the webview server and the event loop.
        Args:
            *args: Additional arguments to pass to the webview.start method.
            **kwargs: Additional keyword arguments to pass to the webview.start method.
        Returns:
            None
        """
        log.debug(f"Running webview.start with args: {args} and kwargs: {kwargs}.")
        webview.start(*args, debug=self.dev_mode, **kwargs)

    def exit(self) -> None:
        """Destroy all windows to end event loop."""
        log.debug("Destroying all windows to end event loop.")
        for window_id in self._windows.keys():
            self.close(window_id)
