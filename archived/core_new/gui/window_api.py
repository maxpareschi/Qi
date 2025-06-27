"""
Window API for Qi.

This module provides API functions for window management that are exposed to
the JavaScript frontend.
"""

from fastapi import APIRouter

from core_new.di import container
from core_new.logger import get_logger

log = get_logger("gui.window_api")


def create_window_router() -> APIRouter:
    """
    Create a FastAPI router for window management.

    Returns:
        A FastAPI router with window management endpoints.
    """
    router = APIRouter(prefix="/window", tags=["window"])

    @router.get("/list")
    async def list_windows():
        """List all windows."""
        window_manager = container.get("window_manager")
        windows = await window_manager.list_windows()
        return {"windows": windows}

    @router.post("/open")
    async def open_window(
        url: str, title: str = "Qi Window", width: int = 800, height: int = 600
    ):
        """Open a new window."""
        window_manager = container.get("window_manager")
        window_id = await window_manager.open_window(
            url=url,
            title=title,
            width=width,
            height=height,
        )
        return {"window_id": window_id}

    @router.post("/close/{window_id}")
    async def close_window(window_id: str):
        """Close a window."""
        window_manager = container.get("window_manager")
        success = await window_manager.close_window(window_id)
        return {"success": success}

    @router.post("/send/{window_id}")
    async def send_to_window(window_id: str, message: dict):
        """Send a message to a window."""
        hub = container.get("hub")
        # Create a message for the window
        message["target"] = [window_id]
        await hub.publish(message)
        return {"success": True}

    return router


def close_window(window):
    """Close a window."""
    window.destroy()


def minimize_window(window):
    """Minimize a window."""
    if not getattr(window, "minimized", False):
        window.minimize()
        setattr(window, "minimized", True)
    else:
        window.restore()
        setattr(window, "minimized", False)


def maximize_window(window):
    """Maximize a window."""
    if not getattr(window, "maximized", False):
        window.maximize()
        setattr(window, "maximized", True)
    else:
        window.restore()
        setattr(window, "maximized", False)


def restore_window(window):
    """Restore a window."""
    window.restore()
    setattr(window, "minimized", False)
    setattr(window, "maximized", False)


def move_window(window, x, y):
    """Move a window."""
    window.move(x, y)
