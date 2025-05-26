from core.gui.bindings import register_window_manager_handlers
from core.gui.window import QiWindow
from core.gui.window_manager import QiWindowManager


def setup_window_manager() -> QiWindowManager:
    """Window manager setup convenience method.
    Creates a window manager instance and binds it to the bus directly.

    Returns:
        QiWindowManager: The window manager instance.
    """

    window_manager = QiWindowManager()
    register_window_manager_handlers(window_manager)
    return window_manager


__all__ = (
    "QiWindowManager",
    "QiWindow",
    "setup_window_manager",
)
