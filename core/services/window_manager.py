import asyncio
import os
import threading
from typing import Any

import webview

from core.services.log import log
from core.services.window import QiWindow


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

    def create_window(
        self,
        *,
        addon: str,
        session: str,
        **kwargs: Any,
    ) -> str:
        """Create a new window.
        Args:
            addon: The addon to create the window for.
            session: The session to create the window for.
            **kwargs: Additional keyword arguments to pass to the window.
        Returns:
            The UUID of the window.
        """

        url = f"http://{os.getenv('QI_LOCAL_SERVER')}:{os.getenv('QI_LOCAL_PORT')}/{addon}"
        log.debug(f"Creating window for {url}")
        window = QiWindow(url, addon=addon, session=session, **kwargs)
        self._windows[window.uuid] = window
        log.debug(f"Activated webview: {self._windows[window.uuid]}")
        return window.uuid

    def list_all(self) -> list[dict]:
        """List all windows.
        Returns:
            A list of dictionaries containing the window UUID and addon.
        """
        log.debug(f"Listing all windows: {self._windows}")
        log.debug(f"Listing all windows: {self._windows}")
        return [
            {"window_uuid": window_uuid, "addon": window.addon}
            for window_uuid, window in self._windows.items()
        ]

    def list_by_addon(self, addon: str) -> list[dict]:
        """List all windows by addon.
        Args:
            addon: The addon to list the windows for.
        Returns:
            A list of dictionaries containing the window UUID and addon.
        """

        return [
            {"window_uuid": window_uuid, "addon": window.addon}
            for window_uuid, window in self._windows.items()
            if window.addon == addon
        ]

    def list_by_session(self, session: str) -> list[dict]:
        """List all windows by session.
        Args:
            session: The session to list the windows for.
        Returns:
            A list of dictionaries containing the window UUID and addon.
        """

        return [
            {"window_uuid": window_uuid, "addon": window.addon}
            for window_uuid, window in self._windows.items()
            if window.session == session
        ]

    def get_window(self, uuid: str) -> QiWindow | None:
        """Get a window by UUID.
        Args:
            uuid: The UUID of the window to get.
        Returns:
            The window if found, otherwise None.
        """

        return self._windows.get(uuid, None)

    def invoke(self, window_uuid: str, method: str, *args):
        """Invoke a method on a window.
        Args:
            window_uuid: The UUID of the window to invoke the method on.
            method: The method to invoke.
            *args: Additional arguments to pass to the method.
        Returns:
            The result of the method.
        """

        win = self._windows[window_uuid]
        fn = getattr(win, method)
        if threading.get_ident() == self._gui_thread:
            return fn(*args)
        loop = asyncio.get_event_loop()
        return loop.call_soon_threadsafe(fn, *args)

    def close(self, window_uuid: str) -> None:
        """Close a window.
        Args:
            window_uuid: The UUID of the window to close.
        Returns:
            The UUID of the window if it was closed, otherwise None.
        """

        win = self._windows.get(window_uuid, None)
        if win:
            win.close()
            del self._windows[window_uuid]
            return window_uuid
        log.warning(f"Window {window_uuid} not found")
        return None

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Run the webview server and the event loop.
        Args:
            *args: Additional arguments to pass to the webview.start method.
            **kwargs: Additional keyword arguments to pass to the webview.start method.
        Returns:
            None
        """

        # webview.start(*args, debug=bool(int(os.getenv("QI_DEV_MODE", "0"))), **kwargs)
        webview.start(*args, debug=True, **kwargs)

    def exit(self) -> None:
        """Destroy all windows to end event loop."""

        for window_uuid in self._windows.keys():
            self.close(window_uuid)
