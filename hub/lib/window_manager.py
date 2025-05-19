import inspect
from typing import Any, Callable

import webview
from webview.window import FixPoint

from core.log import log


class QiWindow:
    def __init__(self):
        self.window: webview.Window | None = None
        self._api_methods: list[Callable] = [
            method
            for name, method in inspect.getmembers(self, predicate=inspect.ismethod)
            if not name.startswith("_")
        ]
        log.debug(
            f"QiWindow exposed api: {[method.__name__ for method in self._api_methods]}"
        )
        self.create: Callable = self._create

    def _on_loaded(self) -> None:
        self.window.events.loaded -= self._on_loaded
        self.show()
        self.window.hidden = False

    def _create(self, *args: Any, **kwargs: Any) -> None:
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

        self.window = webview.create_window(*args, **launch_kwargs)
        self.window.events.loaded += self._on_loaded
        for method in self._api_methods:
            self.window.expose(method)

    def close(self) -> None:
        if self.window:
            self.window.destroy()
            self.window = None

    def minimize(self) -> None:
        if not self.window:
            return
        self.window.minimize()

    def maximize(self) -> None:
        if not self.window:
            return
        if not self.window.maximized:
            self.window.maximize()
            self.window.maximized = True
        else:
            self.window.restore()
            self.window.maximized = False

    def restore(self) -> None:
        if not self.window:
            return
        self.window.restore()
        self.window.maximized = False

    def hide(self) -> None:
        if not self.window:
            return
        self.window.hide()

    def show(self) -> None:
        if not self.window:
            return
        self.window.show()

    def move(self, x: int, y: int) -> None:
        if not self.window:
            return
        self.window.move(x, y)

    def resize(self, width: int, height: int, edge: str) -> None:
        if not self.window:
            return

        anchors = FixPoint.WEST | FixPoint.NORTH

        if edge == "top":
            anchors = FixPoint.SOUTH
        elif edge == "bottom":
            anchors = FixPoint.NORTH
        elif edge == "left":
            anchors = FixPoint.EAST
        elif edge == "right":
            anchors = FixPoint.WEST

        self.window.resize(width, height, anchors)

    def auto_resize(self) -> None:
        if not self.window:
            return

        width, height = self.window.evaluate_js("""
            return [window.innerWidth, window.innerHeight]
        """)

        self.resize(width, height, "handle")


class QiWindowManager:
    def __init__(self):
        self.windows = {}

    def create_window(self, *args: Any, **kwargs: Any) -> None:
        window = QiWindow()
        window.create(*args, **kwargs)
        self.windows[window.window.uid] = {
            "title": window.window.title,
            "url": window.window.real_url,
            "window": window,
        }
        log.debug(f"Activated webview: {self.windows[window.window.uid]}")

    def get_window(self, uid: str) -> QiWindow | None:
        return self.windows.get(uid, None)

    def run(self, *args: Any, **kwargs: Any) -> None:
        webview.start(*args, **kwargs)
