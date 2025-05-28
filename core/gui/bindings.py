from typing import TYPE_CHECKING

from core import logger
from core.gui.manager import QiWindowManager
from core.server.bus import (
    QiEnvelope,
    get_addon_from_source,
    get_session_id_from_source,
    get_window_id_from_source,
    qi_bus,
)

log = logger.get_logger(__name__)

if TYPE_CHECKING:
    pass


def register_window_manager_handlers(wm: QiWindowManager) -> None:
    """Register window manager handlers with the message bus."""

    log.info("Registering bus handlers for window manager.")

    @qi_bus.on("test.ping")
    async def _test_ping(envelope: QiEnvelope) -> None:
        session_id = get_session_id_from_source(envelope)
        addon = get_addon_from_source(envelope)

        await qi_bus.emit(
            "test.pong",
            payload={
                "message": "pong",
                "timestamp": envelope.payload.get("timestamp"),
                "from_session_id": session_id,
                "from_addon": addon,
            },
            reply_to=envelope.message_id,
        )

    @qi_bus.on("test.echo")
    async def _test_echo(envelope: QiEnvelope) -> None:
        session_id = get_session_id_from_source(envelope)
        addon = get_addon_from_source(envelope)

        await qi_bus.emit(
            "test.echo.reply",
            payload={
                "echoed_message": envelope.payload.get("message"),
                "original_timestamp": envelope.payload.get("timestamp"),
                "from_session_id": session_id,
                "from_addon": addon,
            },
            reply_to=envelope.message_id,
        )

    @qi_bus.on("wm.window.open")
    async def _open(envelope: QiEnvelope) -> None:
        session_id = get_session_id_from_source(envelope)
        addon = get_addon_from_source(envelope)

        window_id = wm.create_window(addon=addon, session_id=session_id)
        await qi_bus.emit(
            "wm.window.opened",
            payload={
                "window_id": window_id,
                "addon": addon,
                "session_id": session_id,
            },
        )

    @qi_bus.on("wm.window.list_by_session")
    async def _list_by_session(envelope: QiEnvelope) -> None:
        session_id = get_session_id_from_source(envelope)
        windows = wm.list_by_session_id(session_id)

        await qi_bus.emit(
            "wm.window.listed",
            payload={"windows": windows, "filter": "session", "session_id": session_id},
            reply_to=envelope.message_id,
        )

    @qi_bus.on("wm.window.list_all")
    async def _list_all(envelope: QiEnvelope) -> None:
        windows = wm.list_all()
        await qi_bus.emit(
            "wm.window.listed",
            payload={"windows": windows, "filter": "all"},
            reply_to=envelope.message_id,
        )

    @qi_bus.on("wm.window.close")
    async def _close(envelope: QiEnvelope) -> None:
        window_id = envelope.payload.get("window_id")
        if not window_id:
            return

        closed_window = wm.close(window_id)
        if closed_window:
            await qi_bus.emit(
                "wm.window.closed",
                payload={"window_id": window_id},
            )

    @qi_bus.on("wm.window.invoke")
    async def _invoke(envelope: QiEnvelope) -> None:
        window_id = get_window_id_from_source(envelope)
        method = envelope.payload.get("method")
        args = envelope.payload.get("args", [])

        if not window_id or not method:
            return

        result = wm.invoke(window_id, method, *args)
        await qi_bus.emit(
            "wm.window.invoked",
            payload={
                "window_id": window_id,
                "method": method,
                "result": result,
            },
            reply_to=envelope.message_id,
        )

    # Check which handlers are registered
    qi_bus.list_handlers()  # Check the handlers

    # Add a direct object ID check to verify that we have the correct singleton instance
    log.info(f"Window manager object ID: {id(wm)}")
