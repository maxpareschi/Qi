from core.window_manager.bindings import bind_window_manager_to_bus
from core.window_manager.window import QiWindow
from core.window_manager.window_manager import QiWindowManager


def setup_window_manager() -> QiWindowManager:
    """Window manager setup convenience method.
    Creates a window manager instance and binds it to the bus directly.

    Returns:
        QiWindowManager: The window manager instance.
    """

    window_manager = QiWindowManager()
    bind_window_manager_to_bus(window_manager)
    return window_manager


__all__ = (
    "QiWindowManager",
    "QiWindow",
    "setup_window_manager",
)
