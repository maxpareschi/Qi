import inspect
import uuid
from typing import Any, Callable

import webview
from webview.window import FixPoint

from core import logger

log = logger.get_logger(__name__)


class QiWindow:
    """A Wrapper for webview.Window that autoregisters javascript bridge
    methods to work on windows for a native like experience.
    Needs an addon and a session. They could be made up and always stay
    the same for a single window - no dependency workflow.
    Addon and session are useful in plugin contexts, especially in the
    Qi framework."""

    def __init__(
        self,
        url: str,
        addon: str,
        session: str,
        **kwargs: Any,
    ):
        """Initialize a new window.
        Args:
            url: The URL to load in the window.
            addon: The addon that the window belongs to.
            session: The session that the window belongs to.
            **kwargs: Additional keyword arguments to pass to the webview.Window constructor.
        """

        self.state: dict[str, bool] = {
            "loaded": False,
            "minimized": False,
            "maximized": False,
            "hidden": True,
        }

        self.uuid: str = str(uuid.uuid4())
        self.url: str = url
        self.addon: str = addon
        self.session: str = session
        self.window: webview.Window | None = None

        self._api_methods: list[Callable] = [
            method
            for name, method in inspect.getmembers(self, predicate=inspect.ismethod)
            if not name.startswith("_")
        ]
        log.debug(
            f"QiWindow exposed api: {[method.__name__ for method in self._api_methods]}"
        )
        if not self.window:
            self._create(self.addon, **kwargs)

    def _create(self, title: str, **kwargs: Any) -> None:
        """Create a new window. Gets called automatically on class instantiation.
        Args:
            title: The title of the window.
            **kwargs: Additional keyword arguments to pass to the webview.Window constructor.
        """

        launch_kwargs: dict[str, Any] = kwargs
        launch_kwargs.update(
            {
                "url": self.url,
                "min_size": (400, 300),
                "background_color": "#000000",
                "frameless": True,
                "easy_drag": False,
                "js_api": None,
                "hidden": True,
            }
        )

        self.window = webview.create_window(title, **launch_kwargs)
        self.window.events.loaded += self._on_loaded
        for method in self._api_methods:
            self.window.expose(method)

    def _on_loaded(self) -> None:
        """Event handler for when the window is loaded.
        Shows the window and sets it to not hidden."""

        self.window.events.loaded -= self._on_loaded
        self.show()
        self.state["hidden"] = False

    def get_session(self) -> str:
        """Get the session of the window.
        Returns:
            The session of the window.
        """

        return self.session

    def get_window_uuid(self) -> str:
        """Get the UUID of the window.
        Returns:
            The UUID of the window.
        """

        return self.uuid

    def get_addon(self) -> str:
        """Get the addon of the window.
        Returns:
            The addon of the window.
        """

        return self.addon

    def close(self) -> None:
        """Destroy the window if it exists."""

        if self.window:
            self.window.destroy()
            self.window = None

    def minimize(self) -> None:
        """Minimize the window if it exists."""

        if not self.window:
            return
        self.window.minimize()
        self.state["minimized"] = True

    def maximize(self) -> None:
        """Maximize the window if it exists."""

        if not self.window:
            return
        if not self.state["maximized"]:
            self.window.maximize()
            self.state["maximized"] = True
        else:
            self.window.restore()
            self.state["maximized"] = False

    def restore(self) -> None:
        """Restore the window if it exists."""

        if not self.window:
            return
        self.window.restore()
        self.state["minimized"] = False
        self.state["maximized"] = False
        self.state["hidden"] = False

    def hide(self) -> None:
        """Hide the window if it exists."""

        if not self.window:
            return
        self.window.hide()
        self.state["hidden"] = True

    def show(self) -> None:
        """Show the window if it exists."""

        if not self.window:
            return
        self.window.show()
        self.state["hidden"] = False

    def move(self, x: int, y: int) -> None:
        """Move the window if it exists."""

        if not self.window:
            return
        self.window.move(x, y)

    def resize(self, width: int, height: int, edge: str) -> None:
        """Resize the window if it exists."""

        if not self.window:
            return

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

        self.window.resize(width, height, anchors)

    def auto_resize(self) -> None:
        """Automatically resize the window based on contentif it exists."""

        if not self.window:
            return

        width, height = self.window.evaluate_js("""
            return [window.innerWidth, window.innerHeight]
        """)

        self.resize(width, height, "handle")
