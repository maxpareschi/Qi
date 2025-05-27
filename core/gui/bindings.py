import time

from core import logger
from core.gui.manager import QiWindowManager
from core.server.bus import QiEnvelope, qi_bus

log = logger.get_logger(__name__)


def get_session(envelope: QiEnvelope) -> str:
    """Helper to safely extract session from envelope context."""
    return (
        envelope.context.session
        if envelope.context and envelope.context.session
        else "unknown"
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

        # Send response with the created window
        await qi_bus.emit(
            "wm.window.opened",
            payload={"window_uuid": window_uuid, "addon": addon},
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
            reply_to=envelope.message_id,
        )

    @qi_bus.on("wm.window.list_all")
    async def _list_all(envelope: QiEnvelope) -> None:
        """List all windows."""

        session = get_session(envelope)
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
            reply_to=envelope.message_id,
        )

    @qi_bus.on("wm.window.close")
    async def _close(envelope: QiEnvelope) -> None:
        """Close a window."""

        session = get_session(envelope)
        log.info(f"Closing window {envelope.payload['window_uuid']}")
        wm.close(envelope.payload["window_uuid"])
        await qi_bus.emit(
            "wm.window.closed",
            payload={"window_uuid": envelope.payload["window_uuid"]},
            reply_to=envelope.message_id,
        )

    @qi_bus.on("wm.window.invoke")
    async def _invoke(envelope: QiEnvelope) -> None:
        """Invoke a method on a window."""

        log.info(
            f"Invoking method {envelope.payload['method']} on window {envelope.payload['window_uuid']}"
        )
        wm.invoke(
            envelope.payload["window_uuid"],
            envelope.payload["method"],
            *envelope.payload.get("args", []),
        )

    # Check which handlers are registered
    qi_bus.list_handlers()  # Check the handlers

    # Add a direct object ID check to verify that we have the correct singleton instance
    log.info(f"Window manager object ID: {id(wm)}")
