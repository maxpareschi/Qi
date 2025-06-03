from core.bus import (
    QiEvent,
    QiEventBus,
    get_addon_from_source,
    get_session_id_from_source,
    get_window_id_from_source,
)
from core.gui.window_manager import QiWindowManager
from core.logger import get_logger

log = get_logger(__name__)


def bind_window_manager(wm: QiWindowManager) -> None:
    """Register window manager handlers with the message bus."""

    # Get the singleton bus instance
    bus = QiEventBus()

    @bus.on("test.ping")
    async def _test_ping(envelope: QiEvent) -> None:
        session_id = get_session_id_from_source(envelope)
        addon = get_addon_from_source(envelope)

        await bus.emit(
            "test.pong",
            payload={
                "message": "pong",
                "timestamp": envelope.payload.get("timestamp"),
                "from_session_id": session_id,
                "from_addon": addon,
            },
            reply_to=envelope.message_id,
        )

    @bus.on("test.echo")
    async def _test_echo(envelope: QiEvent) -> None:
        session_id = get_session_id_from_source(envelope)
        addon = get_addon_from_source(envelope)

        await bus.emit(
            "test.echo.reply",
            payload={
                "echoed_message": envelope.payload.get("message"),
                "original_timestamp": envelope.payload.get("timestamp"),
                "from_session_id": session_id,
                "from_addon": addon,
            },
            reply_to=envelope.message_id,
        )

    @bus.on("wm.window.open")
    async def _open(envelope: QiEvent) -> None:
        session_id = get_session_id_from_source(envelope)
        addon = get_addon_from_source(envelope)

        window_id = wm.create_window(addon=addon, session_id=session_id)
        await bus.emit(
            "wm.window.opened",
            payload={
                "window_id": window_id,
                "addon": addon,
                "session_id": session_id,
            },
        )

    @bus.on("wm.window.list_by_session")
    async def _list_by_session(envelope: QiEvent) -> None:
        session_id = get_session_id_from_source(envelope)
        windows = wm.list_by_session_id(session_id)

        await bus.emit(
            "wm.window.listed",
            payload={"windows": windows, "filter": "session", "session_id": session_id},
            reply_to=envelope.message_id,
        )

    @bus.on("wm.window.list_all")
    async def _list_all(envelope: QiEvent) -> None:
        windows = wm.list_all()
        await bus.emit(
            "wm.window.listed",
            payload={"windows": windows, "filter": "all"},
            reply_to=envelope.message_id,
        )

    @bus.on("wm.window.close")
    async def _close(envelope: QiEvent) -> None:
        window_id = envelope.payload.get("window_id")
        if not window_id:
            return

        closed_window = wm.close(window_id)
        if closed_window:
            await bus.emit(
                "wm.window.closed",
                payload={"window_id": window_id},
            )

    @bus.on("wm.window.invoke")
    async def _invoke(envelope: QiEvent) -> None:
        """Invoke a method on a window."""
        if not envelope.payload:
            log.warning("Invoke request missing payload")
            return

        window_id = envelope.payload.get("window_id")
        method = envelope.payload.get("method")
        args = envelope.payload.get("args", [])

        if not window_id or not method:
            log.warning("Invoke request missing window_id or method")
            return

        result = wm.invoke(window_id, method, *args)

        await bus.emit(
            "wm.window.invoked",
            payload={"window_id": window_id, "method": method, "result": result},
            context=envelope.context,
            reply_to=envelope.message_id,
        )

    @bus.on("wm.window.minimize")
    async def _minimize(envelope: QiEvent) -> None:
        """Minimize a window."""
        if not envelope.payload:
            log.warning("Minimize request missing payload")
            return

        window_id = envelope.payload.get("window_id")
        if not window_id:
            log.warning("Minimize request missing window_id")
            return

        window = wm.get_window(window_id)
        if window:
            window.minimize()

            await bus.emit(
                "wm.window.minimized",
                payload={"window_id": window_id, "success": True},
                context=envelope.context,
                reply_to=envelope.message_id,
            )
        else:
            await bus.emit(
                "wm.window.minimized",
                payload={
                    "window_id": window_id,
                    "success": False,
                    "error": "Window not found",
                },
                context=envelope.context,
                reply_to=envelope.message_id,
            )

    @bus.on("wm.window.maximize")
    async def _maximize(envelope: QiEvent) -> None:
        """Maximize or restore a window."""
        if not envelope.payload:
            log.warning("Maximize request missing payload")
            return

        window_id = envelope.payload.get("window_id")
        if not window_id:
            log.warning("Maximize request missing window_id")
            return

        window = wm.get_window(window_id)
        if window:
            # For webview.Window, we can't track state, so we'll use a simple toggle approach
            # The client side should track the maximized state
            try:
                # Try to maximize (webview will handle if already maximized)
                if envelope.payload.get("restore", False):
                    window.restore()
                    maximized = False
                else:
                    window.maximize()
                    maximized = True

                await bus.emit(
                    "wm.window.maximized",
                    payload={
                        "window_id": window_id,
                        "success": True,
                        "maximized": maximized,
                    },
                    context=envelope.context,
                    reply_to=envelope.message_id,
                )
            except Exception as e:
                await bus.emit(
                    "wm.window.maximized",
                    payload={"window_id": window_id, "success": False, "error": str(e)},
                    context=envelope.context,
                    reply_to=envelope.message_id,
                )
        else:
            await bus.emit(
                "wm.window.maximized",
                payload={
                    "window_id": window_id,
                    "success": False,
                    "error": "Window not found",
                },
                context=envelope.context,
                reply_to=envelope.message_id,
            )

    @bus.on("wm.window.restore")
    async def _restore(envelope: QiEvent) -> None:
        """Restore a window."""
        if not envelope.payload:
            log.warning("Restore request missing payload")
            return

        window_id = envelope.payload.get("window_id")
        if not window_id:
            log.warning("Restore request missing window_id")
            return

        window = wm.get_window(window_id)
        if window:
            window.restore()

            await bus.emit(
                "wm.window.restored",
                payload={"window_id": window_id, "success": True},
                context=envelope.context,
                reply_to=envelope.message_id,
            )
        else:
            await bus.emit(
                "wm.window.restored",
                payload={
                    "window_id": window_id,
                    "success": False,
                    "error": "Window not found",
                },
                context=envelope.context,
                reply_to=envelope.message_id,
            )

    @bus.on("wm.window.move")
    async def _move(envelope: QiEvent) -> None:
        """Move a window to specified coordinates."""
        if not envelope.payload:
            log.warning("Move request missing payload")
            return

        window_id = envelope.payload.get("window_id")
        x = envelope.payload.get("x")
        y = envelope.payload.get("y")

        if not window_id or x is None or y is None:
            log.warning("Move request missing required parameters")
            return

        window = wm.get_window(window_id)
        if window:
            window.move(int(x), int(y))

            await bus.emit(
                "wm.window.moved",
                payload={"window_id": window_id, "success": True, "x": x, "y": y},
                context=envelope.context,
                reply_to=envelope.message_id,
            )
        else:
            await bus.emit(
                "wm.window.moved",
                payload={
                    "window_id": window_id,
                    "success": False,
                    "error": "Window not found",
                },
                context=envelope.context,
                reply_to=envelope.message_id,
            )

    @bus.on("wm.window.resize")
    async def _resize(envelope: QiEvent) -> None:
        """Resize a window."""
        if not envelope.payload:
            log.warning("Resize request missing payload")
            return

        window_id = envelope.payload.get("window_id")
        width = envelope.payload.get("width")
        height = envelope.payload.get("height")
        edge = envelope.payload.get("edge", "bottom-right")

        if not window_id or width is None or height is None:
            log.warning("Resize request missing required parameters")
            return

        window = wm.get_window(window_id)
        if window:
            from webview.util import FixPoint

            # Map edge to anchor points (same logic as the old QiWindow.resize)
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

            window.resize(int(width), int(height), anchors)

            await bus.emit(
                "wm.window.resized",
                payload={
                    "window_id": window_id,
                    "success": True,
                    "width": width,
                    "height": height,
                    "edge": edge,
                },
                context=envelope.context,
                reply_to=envelope.message_id,
            )
        else:
            await bus.emit(
                "wm.window.resized",
                payload={
                    "window_id": window_id,
                    "success": False,
                    "error": "Window not found",
                },
                context=envelope.context,
                reply_to=envelope.message_id,
            )

    @bus.on("wm.window.hide")
    async def _hide(envelope: QiEvent) -> None:
        """Hide a window."""
        if not envelope.payload:
            log.warning("Hide request missing payload")
            return

        window_id = envelope.payload.get("window_id")
        if not window_id:
            log.warning("Hide request missing window_id")
            return

        window = wm.get_window(window_id)
        if window:
            window.hide()

            await bus.emit(
                "wm.window.hidden",
                payload={"window_id": window_id, "success": True},
                context=envelope.context,
                reply_to=envelope.message_id,
            )
        else:
            await bus.emit(
                "wm.window.hidden",
                payload={
                    "window_id": window_id,
                    "success": False,
                    "error": "Window not found",
                },
                context=envelope.context,
                reply_to=envelope.message_id,
            )

    @bus.on("wm.window.show")
    async def _show(envelope: QiEvent) -> None:
        """Show a window."""
        if not envelope.payload:
            log.warning("Show request missing payload")
            return

        window_id = envelope.payload.get("window_id")
        if not window_id:
            log.warning("Show request missing window_id")
            return

        window = wm.get_window(window_id)
        if window:
            window.show()

            await bus.emit(
                "wm.window.shown",
                payload={"window_id": window_id, "success": True},
                context=envelope.context,
                reply_to=envelope.message_id,
            )
        else:
            await bus.emit(
                "wm.window.shown",
                payload={
                    "window_id": window_id,
                    "success": False,
                    "error": "Window not found",
                },
                context=envelope.context,
                reply_to=envelope.message_id,
            )

    @bus.on("wm.window.get_id")
    async def _get_window_id(envelope: QiEvent) -> None:
        """Get the window ID from context or reply with current window ID."""
        # This is mainly for compatibility with the JavaScript side
        # Usually the window_id should already be known from the WebSocket connection

        window_id = get_window_id_from_source(envelope)

        await bus.emit(
            "wm.window.id_response",
            payload={"window_id": window_id},
            context=envelope.context,
            reply_to=envelope.message_id,
        )

    @bus.on("wm.window.get_state")
    async def _get_window_state(envelope: QiEvent) -> None:
        """Get the current state of a window."""
        if not envelope.payload:
            log.warning("Get state request missing payload")
            return

        window_id = envelope.payload.get("window_id")
        if not window_id:
            window_id = get_window_id_from_source(envelope)

        if not window_id:
            log.warning("Get state request missing window_id")
            return

        window = wm.get_window(window_id)
        if window:
            await bus.emit(
                "wm.window.state_response",
                payload={
                    "window_id": window_id,
                    "success": True,
                    "addon": window.addon,
                    "session_id": window.session_id,
                },
                context=envelope.context,
                reply_to=envelope.message_id,
            )
        else:
            await bus.emit(
                "wm.window.state_response",
                payload={
                    "window_id": window_id,
                    "success": False,
                    "error": "Window not found",
                },
                context=envelope.context,
                reply_to=envelope.message_id,
            )
