from typing import Any

from core.logging import get_logger
from core.server.bus import qi_bus
from core.window_manager.window_manager import QiWindowManager

log = get_logger(__name__)


def bind_window_manager_to_bus(wm: QiWindowManager) -> None:
    """Subscribes to the window manager events,
    executes relevant commands, replies to the bus."""

    log.info("BINDING WINDOW MANAGER TO BUS")

    # Register a simple test handler to verify pattern matching works
    @qi_bus.on("test.ping")
    async def _test_ping(
        topic: str, payload: dict[str, Any] | Any | None, session: str
    ) -> None:
        log.info(
            f"TEST PING HANDLER CALLED with topic={topic}, payload={payload}, session={session}"
        )
        await qi_bus.emit("test.pong", {"received": payload}, session=session)

    # Verify this handler is registered
    log.info("Registered test.ping handler")

    @qi_bus.on("wm.window.open")
    async def _open(
        topic: str, payload: dict[str, Any] | Any | None, session: str
    ) -> None:
        """Open a new window against a session."""

        addon = payload.get(
            "addon", "addon-skeleton"
        )  # Default to addon-skeleton if not specified
        log.info(f"Opening window for addon {addon} in session {session}")
        window_uuid = wm.create_window(addon=addon, session=session)
        log.info(f"Created window with UUID: {window_uuid}")

        # Send response with the created window
        await qi_bus.emit(
            "wm.window.opened",
            {"window_uuid": window_uuid, "addon": addon},
            session=session,
        )

    @qi_bus.on("wm.window.list_by_session")
    async def _list_by_session(
        topic: str, payload: dict[str, Any] | Any | None, session: str
    ) -> None:
        """List all windows for a session."""

        log.info(f"Listing windows for session {session}")
        windows = wm.list_by_session(session)
        log.info(f"Found windows: {windows}")

        await qi_bus.emit(
            "wm.window.listed",
            {"windows": windows},
            session=session,
        )

    @qi_bus.on("wm.window.list_all")
    async def _list_all(
        topic: str, payload: dict[str, Any] | Any | None, session: str
    ) -> None:
        """List all windows."""

        log.info("Listing all windows")
        windows = wm.list_all()
        log.info(f"Found windows: {windows}")

        await qi_bus.emit(
            "wm.window.listed",
            {"windows": windows},
            session=session,
        )

    @qi_bus.on("wm.window.close")
    async def _close(
        topic: str, payload: dict[str, Any] | Any | None, session: str
    ) -> None:
        """Close a window."""

        log.info(f"Closing window {payload['window_uuid']}")
        wm.close(payload["window_uuid"])
        await qi_bus.emit(
            "wm.window.closed",
            {"window_uuid": payload["window_uuid"]},
            session=session,
        )

    @qi_bus.on("wm.window.invoke")
    async def _invoke(
        topic: str, payload: dict[str, Any] | Any | None, session: str
    ) -> None:
        """Invoke a method on a window."""

        log.info(
            f"Invoking method {payload['method']} on window {payload['window_uuid']}"
        )
        wm.invoke(payload["window_uuid"], payload["method"], *payload.get("args", []))

    # Check which handlers are registered
    qi_bus.list_handlers()  # Check the handlers

    # Add a direct object ID check to verify that we have the correct singleton instance
    log.info(f"Window manager object ID: {id(wm)}")
