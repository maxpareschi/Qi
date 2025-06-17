"""A module of simple functions to be exposed to the JavaScript frontend."""

from __future__ import annotations

from typing import TYPE_CHECKING

from webview.window import FixPoint

if TYPE_CHECKING:
    import webview


def close(window: webview.Window) -> None:
    """Close the window."""
    window.destroy()


def minimize(window: webview.Window) -> None:
    """Minimize the window."""
    window.minimize()


def maximize(window: webview.Window) -> None:
    """Maximize or restore the window."""
    if not window.maximized:
        window.maximize()
    else:
        window.restore()


def restore(window: webview.Window) -> None:
    """Restore the window."""
    window.restore()


def hide(window: webview.Window) -> None:
    """Hide the window."""
    window.hide()


def show(window: webview.Window) -> None:
    """Show the window."""
    window.show()


def move(window: webview.Window, x: int, y: int) -> None:
    """Move the window."""
    window.move(x, y)


def resize(window: webview.Window, width: int, height: int, edge: str) -> None:
    """Resize the window from a given edge."""
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
