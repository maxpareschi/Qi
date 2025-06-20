"""
Window Manager for Qi.

This module provides a window manager that handles the creation and management
of application windows using webview.
"""

import asyncio
import os
import uuid
from typing import Dict, List, Optional

import webview
from webview.window import FixPoint

from core_new.abc import ManagerBase
from core_new.config import app_config
from core_new.di import container
from core_new.logger import get_logger

log = get_logger("gui.window_manager")


class WindowManager(ManagerBase):
    """
    Manager for application windows.

    This class provides a unified interface for creating and managing windows.
    """

    def __init__(self):
        """Initialize the window manager."""
        self._windows: Dict[str, webview.Window] = {}
        self._lock = asyncio.Lock()
        self._server_host: Optional[str] = None
        self._server_port: Optional[int] = None
        self._icon_path: Optional[str] = None
        self._main_loop_started = asyncio.Event()

    async def initialize(self) -> None:
        """
        Initialize the window manager.

        Args:
            server_host: The host of the server.
            server_port: The port of the server.
        """
        server_manager = container.get("server_manager")
        async with self._lock:
            self._server_host = server_manager.host
            self._server_port = server_manager.port

        # Set default icon path
        base_path = app_config.base_path
        icon_path = os.path.join(base_path, "resources", "qi-icons", "qi_512.png")
        if os.path.exists(icon_path):
            self._icon_path = icon_path.replace("\\", "/")
            log.debug(f"Using icon path: {self._icon_path}")

    async def start(self) -> None:
        """
        Start the webview event loop in a separate thread.

        This method blocks until all windows are closed.

        Args:
            debug: Whether to run in debug mode.
        """
        log.info(f"Starting webview event loop with debug={app_config.dev_mode}")
        loop = asyncio.get_running_loop()

        # Create a future to track when webview is ready
        webview_ready = asyncio.Future()

        def start_webview():
            try:
                # Set the future to indicate webview is starting
                loop.call_soon_threadsafe(webview_ready.set_result, True)
                webview.start(debug=app_config.dev_mode)
            except Exception as e:
                loop.call_soon_threadsafe(webview_ready.set_exception, e)

        # Start webview in executor
        loop.run_in_executor(None, start_webview)

        # Wait for webview to be ready before proceeding
        await webview_ready
        self._main_loop_started.set()
        log.info("Webview event loop started.")

    async def shutdown(self) -> None:
        """Closes all windows, which will terminate the webview event loop."""
        await self.close_all_windows()
        log.info("All windows closed, webview loop will terminate.")

    def _get_server_url(self) -> str:
        """
        Get the URL of the server.

        Returns:
            The URL of the server.

        Raises:
            RuntimeError: If the window manager is not initialized.
        """
        if not self._server_host or not self._server_port:
            raise RuntimeError("Window manager not initialized")
        return f"http://{self._server_host}:{self._server_port}"

    async def open_window(
        self,
        url: str,
        title: str = "Qi",
        window_id: Optional[str] = None,
        width: int = 800,
        height: int = 600,
        x: Optional[int] = None,
        y: Optional[int] = None,
        resizable: bool = True,
        fullscreen: bool = False,
        min_size: tuple = (400, 300),
        hidden: bool = False,
        frameless: bool = True,
        easy_drag: bool = False,
    ) -> str:
        """
        Open a new window.

        Args:
            url: The URL to open in the window.
            title: The title of the window.
            window_id: A unique ID for the window. If not provided, a UUID will be generated.
            width: The width of the window.
            height: The height of the window.
            x: The x position of the window.
            y: The y position of the window.
            resizable: Whether the window is resizable.
            fullscreen: Whether the window is fullscreen.
            min_size: The minimum size of the window.
            hidden: Whether the window is hidden initially.
            frameless: Whether the window is frameless.
            easy_drag: Whether the window can be dragged easily.

        Returns:
            The ID of the new window.
        """
        # Ensure the main loop has been started before creating a window
        await self._main_loop_started.wait()

        window_id = window_id or str(uuid.uuid4())

        # Check if window with this ID already exists
        async with self._lock:
            if window_id in self._windows:
                log.warning(f"Window with ID {window_id} already exists")
                return window_id

        # If URL is relative, prepend the server URL
        if not url.startswith(("http://", "https://")):
            url = f"{self._get_server_url()}/{url.lstrip('/')}"

        # Append session and window IDs as query parameters
        # This is crucial for the frontend to identify itself to the backend hub
        separator = "&" if "?" in url else "?"
        url_with_params = (
            f"{url}{separator}window_id={window_id}&session_id={window_id}"
        )

        # Create the window
        try:
            # We create the window in a separate thread to avoid blocking
            window = await asyncio.to_thread(
                webview.create_window,
                title=title,
                url=url_with_params,
                width=width,
                height=height,
                x=x,
                y=y,
                resizable=resizable,
                fullscreen=fullscreen,
                min_size=min_size,
                hidden=hidden,
                frameless=frameless,
                easy_drag=easy_drag,
                background_color="#000000",
                js_api=None,
            )

            async with self._lock:
                self._windows[window_id] = window

            # Register window API functions
            self._register_window_api(window)

            log.info(f"Created window '{window_id}' with URL '{url_with_params}'")
            return window_id

        except Exception as e:
            log.error(f"Error creating window: {e}", exc_info=True)
            return ""

    def _register_window_api(self, window: webview.Window) -> None:
        """
        Register API functions for the window.

        Args:
            window: The window to register API functions for.
        """
        window.expose(lambda: window.destroy(), name="close")
        window.expose(self._minimize_window(window), name="minimize")
        window.expose(self._maximize_window(window), name="maximize")
        window.expose(self._restore_window(window), name="restore")
        window.expose(lambda: window.hide(), name="hide")
        window.expose(lambda: window.show(), name="show")
        window.expose(lambda x, y: window.move(x, y), name="move")
        window.expose(self._resize_window(window), name="resize")

    def _minimize_window(self, window: webview.Window):
        """
        Create a function to minimize or restore a window.

        Args:
            window: The window to minimize or restore.

        Returns:
            A function that minimizes or restores the window.
        """

        def minimize():
            if not getattr(window, "minimized", False):
                window.minimize()
                setattr(window, "minimized", True)
            else:
                window.restore()
                setattr(window, "minimized", False)

        return minimize

    def _maximize_window(self, window: webview.Window):
        """
        Create a function to maximize or restore a window.

        Args:
            window: The window to maximize or restore.

        Returns:
            A function that maximizes or restores the window.
        """

        def maximize():
            if not getattr(window, "maximized", False):
                window.maximize()
                setattr(window, "maximized", True)
            else:
                window.restore()
                setattr(window, "maximized", False)

        return maximize

    def _restore_window(self, window: webview.Window):
        """
        Create a function to restore a window.

        Args:
            window: The window to restore.

        Returns:
            A function that restores the window.
        """

        def restore():
            window.restore()
            setattr(window, "minimized", False)
            setattr(window, "maximized", False)

        return restore

    def _resize_window(self, window: webview.Window):
        """
        Create a function to resize a window.

        Args:
            window: The window to resize.

        Returns:
            A function that resizes the window.
        """

        def resize(width: int, height: int, edge: str = "bottom-right"):
            anchors = FixPoint.WEST | FixPoint.NORTH
            match edge:
                case "top":
                    anchors = FixPoint.SOUTH
                case "bottom":
                    anchors = FixPoint.NORTH
                case "left":
                    anchors = FixPoint.EAST
                case "right":
                    anchors = FixPoint.WEST
                case "bottom-right":
                    anchors = FixPoint.WEST | FixPoint.NORTH
                case "bottom-left":
                    anchors = FixPoint.EAST | FixPoint.NORTH
                case "top-right":
                    anchors = FixPoint.WEST | FixPoint.SOUTH
                case "top-left":
                    anchors = FixPoint.EAST | FixPoint.SOUTH
            window.resize(width, height, anchors)

        return resize

    async def list_windows(self) -> List[Dict[str, str]]:
        """Returns a list of active windows with their ID and title."""
        windows = []
        async with self._lock:
            for window_id, window in self._windows.items():
                windows.append(
                    {
                        "id": window_id,
                        "title": window.title,
                    }
                )
        return windows

    async def get_window(self, window_id: str) -> Optional[webview.Window]:
        """
        Get a window by its ID.

        Args:
            window_id: The ID of the window.

        Returns:
            The window, or None if not found.
        """
        async with self._lock:
            return self._windows.get(window_id)

    async def close_window(self, window_id: str) -> bool:
        """
        Close a window by its ID.

        Args:
            window_id: The ID of the window.

        Returns:
            True if the window was closed, False otherwise.
        """
        window = await self.get_window(window_id)
        if not window:
            return False

        try:
            # Running destroy in a thread is safer as it can block
            await asyncio.to_thread(window.destroy)
            async with self._lock:
                if window_id in self._windows:
                    del self._windows[window_id]
            log.info(f"Closed window '{window_id}'")
            return True
        except Exception as e:
            log.error(f"Error closing window '{window_id}': {e}", exc_info=True)
            return False

    async def close_all_windows(self) -> None:
        """Close all open windows."""
        async with self._lock:
            window_ids = list(self._windows.keys())

        for window_id in window_ids:
            await self.close_window(window_id)

    def run(self, debug: bool = False) -> None:
        """
        DEPRECATED: The main loop is now started via the `start` method.
        This method is kept for backward compatibility but does nothing.
        """
        log.warning(
            "WindowManager.run() is deprecated. The event loop is managed by Application."
        )
        pass


# Create a global window manager instance
window_manager = WindowManager()

# Register the window manager as a singleton service
container.register_instance("window_manager", window_manager)
