from core.services.connection_manager import connection_manager
from core.services.log import log
from core.services.window_manager import QiWindowManager


def bind_window_manager_to_bus(wm: QiWindowManager):
    """Subscribes to the window manager events,
    executes relevant commands, replies to the bus."""

    log.info("BINDING WINDOW MANAGER TO BUS")

    # Register a simple test handler to verify pattern matching works
    @connection_manager.subscribe("test.ping")
    async def _test_ping(topic, payload, session):
        log.info(
            f"TEST PING HANDLER CALLED with topic={topic}, payload={payload}, session={session}"
        )
        await connection_manager.push(
            "test.pong", {"received": payload}, session=session
        )

    # Verify this handler is registered
    log.info("Registered test.ping handler")

    @connection_manager.subscribe("wm.window.open")
    async def _open(topic, payload, session):
        """Open a new window against a session."""

        addon = payload.get(
            "addon", "addon-skeleton"
        )  # Default to addon-skeleton if not specified
        log.info(f"Opening window for addon {addon} in session {session}")
        window_uuid = wm.create_window(addon=addon, session=session)
        log.info(f"Created window with UUID: {window_uuid}")

        # Send response with the created window
        await connection_manager.push(
            "wm.window.opened",
            {"window_uuid": window_uuid, "addon": addon},
            session=session,
        )

    @connection_manager.subscribe("wm.window.list_by_session")
    async def _list_by_session(topic, payload, session):
        """List all windows for a session."""

        log.info(f"Listing windows for session {session}")
        windows = wm.list_by_session(session)
        log.info(f"Found windows: {windows}")

        await connection_manager.push(
            "wm.window.listed",
            {"windows": windows},
            session=session,
        )

    @connection_manager.subscribe("wm.window.list_all")
    async def _list_all(topic, payload, session):
        """List all windows."""

        log.info("Listing all windows")
        windows = wm.list_all()
        log.info(f"Found windows: {windows}")

        await connection_manager.push(
            "wm.window.listed",
            {"windows": windows},
            session=session,
        )

    @connection_manager.subscribe("wm.window.close")
    async def _close(topic, payload, session):
        """Close a window."""

        log.info(f"Closing window {payload['window_uuid']}")
        wm.close(payload["window_uuid"])
        await connection_manager.push(
            "wm.window.closed",
            {"window_uuid": payload["window_uuid"]},
            session=session,
        )

    @connection_manager.subscribe("wm.window.invoke")
    def _invoke(topic, payload, session):
        """Invoke a method on a window."""

        log.info(
            f"Invoking method {payload['method']} on window {payload['window_uuid']}"
        )
        wm.invoke(payload["window_uuid"], payload["method"], *payload.get("args", []))

    # Check which handlers are registered
    connection_manager.list_handlers()  # Check the handlers

    # Add a direct object ID check to verify that we have the correct singleton instance
    log.info(f"Connection manager object ID: {id(connection_manager)}")
