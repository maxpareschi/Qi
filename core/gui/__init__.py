from core.gui.bindings import register_window_manager_handlers
from core.gui.manager import QiWindowManager
from core.gui.window import QiWindow


def setup_window_manager() -> QiWindowManager:
    """Window manager setup convenience method.
    Creates a window manager instance and binds it to the bus directly.

    Returns:
        QiWindowManager: The window manager instance.
    """

    window_manager = QiWindowManager()
    register_window_manager_handlers(window_manager)
    return window_manager


# Singleton instance will be created lazily to avoid circular imports
window_manager = None


__all__ = (
    "QiWindowManager",
    "QiWindow",
    "setup_window_manager",
    "window_manager",
)
