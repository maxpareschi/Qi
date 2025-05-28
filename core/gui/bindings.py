import time

from core import logger
from core.gui.manager import QiWindowManager
from core.server.bus import QiEnvelope, qi_bus

log = logger.get_logger(__name__)


def get_session(envelope: QiEnvelope) -> str:
    """Helper to safely extract session from envelope source."""
    return (
        envelope.source.session
        if envelope.source and envelope.source.session
        else "unknown"
    )


def get_window_uuid(envelope: QiEnvelope) -> str | None:
    """Helper to safely extract window_uuid from envelope source."""
    return (
        envelope.source.window_uuid
        if envelope.source and envelope.source.window_uuid
        else None
    )


def register_window_manager_handlers(wm: QiWindowManager) -> None:
    """Subscribes to the window manager events,
    executes relevant commands, replies to the bus."""

    log.info("Registering bus handlers for window manager.")

    @qi_bus.on("test.ping")
    async def _test_ping(envelope: QiEnvelope) -> None:
        session = get_session(envelope)
        log.debug(f"Ping from {session}")
        await qi_bus.emit(
            "test.pong",
            payload={"received": envelope.payload},
            context=envelope.context,
            source=envelope.source,
            user=envelope.user,
            reply_to=envelope.message_id,
        )

    @qi_bus.on("test.echo")
    async def _test_echo(envelope: QiEnvelope) -> None:
        session = get_session(envelope)
        log.debug(
            f"Echo request: {envelope.payload.get('message', 'No message')} from {session}"
        )
        await qi_bus.emit(
            "test.echo.reply",
            payload={
                "original_message": envelope.payload.get("message", ""),
                "server_timestamp": time.time(),
            },
            context=envelope.context,
            source=envelope.source,
            user=envelope.user,
            reply_to=envelope.message_id,
        )

    @qi_bus.on("wm.window.open")
    async def _open(envelope: QiEnvelope) -> None:
        """Open a new window against a session."""

        session = get_session(envelope)
        addon = envelope.payload.get(
            "addon", "addon-skeleton"
        )  # Default to addon-skeleton if not specified
        log.info(f"Opening window for addon {addon} in session {session}")
        window_uuid = wm.create_window(addon=addon, session=session)
        log.info(f"Created window with UUID: {window_uuid}")

        # Send response with the created window, inheriting context and user
        await qi_bus.emit(
            "wm.window.opened",
            payload={"window_uuid": window_uuid, "addon": addon},
            context=envelope.context,
            source={"session": session, "addon": addon},
            user=envelope.user,
            reply_to=envelope.message_id,
        )

    @qi_bus.on("wm.window.list_by_session")
    async def _list_by_session(envelope: QiEnvelope) -> None:
        """List all windows for a session."""

        session = get_session(envelope)
        log.info(f"Listing windows for session {session}")
        windows = wm.list_by_session(session)
        log.info(f"Found windows: {windows}")

        await qi_bus.emit(
            "wm.window.listed",
            payload={"windows": windows},
            context=envelope.context,
            source=envelope.source,
            user=envelope.user,
            reply_to=envelope.message_id,
        )

    @qi_bus.on("wm.window.list_all")
    async def _list_all(envelope: QiEnvelope) -> None:
        """List all windows."""

        windows = wm.list_all()

        # Debug: Check bus vs window manager tracking
        bus_sessions = list(qi_bus._sessions.keys())
        bus_windows = {s: list(w.keys()) for s, w in qi_bus._windows.items()}
        log.debug(f"Window manager: {len(windows)} windows")
        log.debug(f"Bus sessions: {bus_sessions}")
        log.debug(f"Bus windows: {bus_windows}")

        await qi_bus.emit(
            "wm.window.listed",
            payload={"windows": windows},
            context=envelope.context,
            source=envelope.source,
            user=envelope.user,
            reply_to=envelope.message_id,
        )

    @qi_bus.on("wm.window.close")
    async def _close(envelope: QiEnvelope) -> None:
        """Close a window."""

        try:
            window_uuid = envelope.payload["window_uuid"]
            log.info(f"Closing window {window_uuid}")

            result = wm.close(window_uuid)
            if result:
                await qi_bus.emit(
                    "wm.window.closed",
                    payload={"window_uuid": window_uuid, "closed_by": "request"},
                    context=envelope.context,
                    source=envelope.source,
                    user=envelope.user,
                    reply_to=envelope.message_id,
                )
            else:
                await qi_bus.emit(
                    "wm.window.close_failed",
                    payload={"window_uuid": window_uuid, "error": "Window not found"},
                    context=envelope.context,
                    source=envelope.source,
                    user=envelope.user,
                    reply_to=envelope.message_id,
                )
        except KeyError:
            log.error("Missing window_uuid in close request")
            await qi_bus.emit(
                "wm.window.close_failed",
                payload={"error": "Missing window_uuid"},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )

    @qi_bus.on("wm.window.invoke")
    async def _invoke(envelope: QiEnvelope) -> None:
        """Invoke a method on a window."""

        try:
            window_uuid = envelope.payload["window_uuid"]
            method = envelope.payload["method"]
            args = envelope.payload.get("args", [])

            log.info(f"Invoking method {method} on window {window_uuid}")
            result = wm.invoke(window_uuid, method, *args)

            await qi_bus.emit(
                "wm.window.invoked",
                payload={
                    "window_uuid": window_uuid,
                    "method": method,
                    "result": result,
                },
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )
        except KeyError as e:
            log.error(f"Missing required field in invoke request: {e}")
            await qi_bus.emit(
                "wm.window.invoke_failed",
                payload={"error": f"Missing required field: {e}"},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )
        except Exception as e:
            log.error(f"Failed to invoke method on window: {e}")
            await qi_bus.emit(
                "wm.window.invoke_failed",
                payload={"error": str(e)},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )

    # Window operation handlers - replacing direct callbacks
    @qi_bus.on("wm.window.minimize")
    async def _minimize(envelope: QiEnvelope) -> None:
        """Minimize a window."""
        try:
            window_uuid = envelope.payload["window_uuid"]
            log.info(f"Minimizing window {window_uuid}")
            wm.invoke(window_uuid, "minimize")
            await qi_bus.emit(
                "wm.window.minimized",
                payload={"window_uuid": window_uuid},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )
        except KeyError:
            log.error("Missing window_uuid in minimize request")
            await qi_bus.emit(
                "wm.window.operation_failed",
                payload={"error": "Missing window_uuid", "operation": "minimize"},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )
        except Exception as e:
            log.error(f"Failed to minimize window: {e}")
            await qi_bus.emit(
                "wm.window.operation_failed",
                payload={"error": str(e), "operation": "minimize"},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )

    @qi_bus.on("wm.window.maximize")
    async def _maximize(envelope: QiEnvelope) -> None:
        """Maximize a window."""
        try:
            window_uuid = envelope.payload["window_uuid"]
            log.info(f"Maximizing window {window_uuid}")
            wm.invoke(window_uuid, "maximize")
            await qi_bus.emit(
                "wm.window.maximized",
                payload={"window_uuid": window_uuid},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )
        except (KeyError, Exception) as e:
            await qi_bus.emit(
                "wm.window.operation_failed",
                payload={"error": str(e), "operation": "maximize"},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )

    @qi_bus.on("wm.window.restore")
    async def _restore(envelope: QiEnvelope) -> None:
        """Restore a window."""
        try:
            window_uuid = envelope.payload["window_uuid"]
            log.info(f"Restoring window {window_uuid}")
            wm.invoke(window_uuid, "restore")
            await qi_bus.emit(
                "wm.window.restored",
                payload={"window_uuid": window_uuid},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )
        except (KeyError, Exception) as e:
            await qi_bus.emit(
                "wm.window.operation_failed",
                payload={"error": str(e), "operation": "restore"},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )

    @qi_bus.on("wm.window.hide")
    async def _hide(envelope: QiEnvelope) -> None:
        """Hide a window."""
        try:
            window_uuid = envelope.payload["window_uuid"]
            log.info(f"Hiding window {window_uuid}")
            wm.invoke(window_uuid, "hide")
            await qi_bus.emit(
                "wm.window.hidden",
                payload={"window_uuid": window_uuid},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )
        except (KeyError, Exception) as e:
            await qi_bus.emit(
                "wm.window.operation_failed",
                payload={"error": str(e), "operation": "hide"},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )

    @qi_bus.on("wm.window.show")
    async def _show(envelope: QiEnvelope) -> None:
        """Show a window."""
        try:
            window_uuid = envelope.payload["window_uuid"]
            log.info(f"Showing window {window_uuid}")
            wm.invoke(window_uuid, "show")
            await qi_bus.emit(
                "wm.window.shown",
                payload={"window_uuid": window_uuid},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )
        except (KeyError, Exception) as e:
            await qi_bus.emit(
                "wm.window.operation_failed",
                payload={"error": str(e), "operation": "show"},
                context=envelope.context,
                source=envelope.source,
                user=envelope.user,
                reply_to=envelope.message_id,
            )

    # Handler for user-initiated window closure
    @qi_bus.on("wm.window.closed_by_user")
    async def _window_closed_by_user(envelope: QiEnvelope) -> None:
        """Handle window closed by user - cleanup and notify."""
        window_uuid = envelope.payload["window_uuid"]
        session = get_session(envelope)
        log.info(f"Window {window_uuid} closed by user in session {session}")

        # Clean up window tracking in manager
        if hasattr(wm, "_on_window_closed"):
            wm._on_window_closed(window_uuid)

        # Broadcast closure notification
        await qi_bus.emit(
            "wm.window.closed",
            payload={"window_uuid": window_uuid, "closed_by": "user"},
            context=envelope.context,
            source=envelope.source,
            user=envelope.user,
        )

    # Check which handlers are registered
    qi_bus.list_handlers()  # Check the handlers

    # Add a direct object ID check to verify that we have the correct singleton instance
    log.info(f"Window manager object ID: {id(wm)}")
