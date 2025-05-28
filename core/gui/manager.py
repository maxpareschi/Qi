import os
import threading
import uuid
from typing import Any

import webview

from core import logger
from core.gui.window import QiWindow

log = logger.get_logger(__name__)

qi_dev_mode = os.getenv("QI_DEV_MODE", "0") == "1"


class QiWindowManager:
    """A manager for windows that handles the creation, management,
    and destruction of windows. Has a thread safe event loop for
    invoking methods on windows and some convenience methods.
    Also has a run method that starts the webview server and
    the event loop.
    """

    def __init__(self):
        """Initialize the window manager."""

        self._windows: dict[str, QiWindow] = {}
        self._gui_thread = threading.get_ident()
        self.dev_mode = qi_dev_mode

    def _on_window_closed(self, window_id: str) -> None:
        """Callback for when a window is closed by the user.
        Cleans up the window tracking."""

        log.debug(f"Cleaning up window {window_id[:8]}... from manager")
        self._windows.pop(window_id, None)

    def create_window(
        self,
        *,
        addon: str,
        session_id: str,
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

        window_id = str(uuid.uuid4())
        log.info(
            f"Creating window {window_id} for addon '{addon}' in session '{session_id}'"
        )

        # Determine the URL for the window
        if self.dev_mode:
            # Development mode: use Vite dev server
            url = f"http://127.0.0.1:5173/{addon}?session_id={session_id}&window_id={window_id}"
            log.debug(f"Development URL: {url}")
        else:
            # Production mode: use built static files
            url = f"http://127.0.0.1:8000/{addon}?session_id={session_id}&window_id={window_id}"
            log.debug(f"Production URL: {url}")

        # Create the window instance
        window = QiWindow(
            url=url,
            addon=addon,
            session_id=session_id,
            window_id=window_id,
            on_close_callback=self._on_window_closed,
            **kwargs,
        )

        # Store in registry
        self._windows[window_id] = window

        log.info(f"Window {window_id} created successfully")
        return window_id

    def list_all(self) -> list[dict]:
        """
        List all active windows.

        Returns:
            List of window information dictionaries
        """
        windows = []
        for window_id, window in self._windows.items():
            windows.append(
                {
                    "window_id": window_id,
                    "addon": window.addon,
                    "session_id": window.session_id,
                }
            )
        return windows

    def list_by_addon(self, addon: str) -> list[dict]:
        """
        List all windows for a specific addon.

        Args:
            addon: The addon name to filter by

        Returns:
            List of window information dictionaries
        """
        windows = []
        for window_id, window in self._windows.items():
            if window.addon == addon:
                windows.append(
                    {
                        "window_id": window_id,
                        "addon": window.addon,
                        "session_id": window.session_id,
                    }
                )
        return windows

    def list_by_session_id(self, session_id: str) -> list[dict]:
        """
        List all windows for a specific session_id.

        Args:
            session_id: The session identifier to filter by

        Returns:
            List of window information dictionaries
        """
        windows = []
        for window_id, window in self._windows.items():
            if window.session_id == session_id:
                windows.append(
                    {
                        "window_id": window_id,
                        "addon": window.addon,
                        "session_id": window.session_id,
                    }
                )
        return windows

    def get_window(self, window_id: str) -> QiWindow | None:
        """
        Get a window instance by its window_id.

        Args:
            window_id: The window identifier

        Returns:
            The window instance, or None if not found
        """
        return self._windows.get(window_id)

    def invoke(self, window_id: str, method: str, *args):
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
        if window:
            if hasattr(window, method):
                return getattr(window, method)(*args)
            else:
                log.warning(f"Method '{method}' not found on window {window_id}")
                return None
        else:
            log.warning(f"Window {window_id} not found for method invocation")
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
            log.info(f"Closing window {window_id}")
            window.close()
            return window_id
        else:
            log.warning(f"Window {window_id} not found for closing")
            return None

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Run the webview server and the event loop.
        Args:
            *args: Additional arguments to pass to the webview.start method.
            **kwargs: Additional keyword arguments to pass to the webview.start method.
        Returns:
            None
        """

        webview.start(*args, debug=qi_dev_mode, **kwargs)
        # webview.start(*args, debug=True, **kwargs)

    def exit(self) -> None:
        """Destroy all windows to end event loop."""

        for window_id in self._windows.keys():
            self.close(window_id)
