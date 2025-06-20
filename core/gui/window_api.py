# core/gui/window_api.py

"""
A module of simple functions to be exposed to the JavaScript frontend.
"""

from webview import Window
from webview.window import FixPoint


def close(window: Window) -> None:
    """Close the window."""
    window.destroy()


def minimize(window: Window) -> None:
    """Minimize the window."""
    if not window.minimized:
        window.minimize()
        window.minimized = True
    else:
        window.restore()
        window.minimized = False


def maximize(window: Window) -> None:
    """Maximize or restore the window."""
    if not window.maximized:
        window.maximize()
        window.maximized = True
    else:
        window.restore()
        window.maximized = False


def restore(window: Window) -> None:
    """Restore the window."""
    window.restore()
    window.minimized = False
    window.maximized = False


def hide(window: Window) -> None:
    """Hide the window."""
    window.hide()
    window.hidden = True


def show(window: Window) -> None:
    """Show the window."""
    window.show()
    window.hidden = False


def move(window: Window, x: int, y: int) -> None:
    """Move the window."""
    window.move(x, y)


def resize(window: Window, width: int, height: int, edge: str) -> None:
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
