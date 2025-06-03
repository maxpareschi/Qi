# core/messaging/hub.py

import asyncio
from typing import Any, Final

from core.bases.models import QiMessage, QiSession
from core.constants import HUB_ID
from core.logger import get_logger
from core.messaging.message_bus import QiMessageBus

log = get_logger(__name__)


class QiHub:
    """
    Facade (“hub”) that exposes a simple API to developers:
      • register(socket=..., session=...)
      • unregister(session_id=...)
      • publish(message=...)
      • request(...)
      • on(topic, session_id=...)
      • on_event(event_name, session_id=...)

    Under the hood, QiHub owns exactly one QiMessageBus instance and forwards
    calls (or decorators) to it. This is where addons and other modules interact
    with the message bus.

    Usage example:

        # in some addon initialization code:
        @hub.on("my.topic", session_id="my-addon-session")
        async def handle_my_topic(message: QiMessage):
            ...

        # somewhere else:
        response = await hub.request(
            topic="my.topic",
            payload={"foo": "bar"},
            session_id="my-other-session"
        )
    """

    def __init__(self) -> None:
        self._bus = QiMessageBus()
        # event_name → [callback_fn]
        self._event_hooks: dict[str, list[Any]] = {}

    ########### SESSION LIFECYCLE (Facade) ###########

    async def register(self, *, socket: Any, session: QiSession) -> None:
        """
        Called by the WebSocket endpoint immediately after handshake.
        Registers a new session in the bus.

        Args:
            socket:  the accepted WebSocket
            session: a QiSession object
        """
        await self._bus.register(socket=socket, session=session)
        # Fire any "register" hooks
        await self._fire(event_name="register", *(session,))

    async def unregister(self, *, session_id: str) -> None:
        """
        Called by the WebSocket endpoint when the client disconnects.
        Unregisters from the bus.

        Args:
            session_id: the low‐level session ID to tear down
        """
        await self._bus.unregister(session_id=session_id)
        # Fire any "unregister" hooks
        await self._fire(event_name="unregister", *(session_id,))

    ########### HANDLER SUBSCRIPTION (Facade) ###########

    def on(self, topic: str, *, session_id: str = HUB_ID):
        """
        Decorator shortcut for subscribing to a topic.

        Example:
            @hub.on("some.topic", session_id="my-session")
            async def my_handler(message: QiMessage):
                ...
        """
        return self._bus.on(topic=topic, session_id=session_id)

    def on_event(self, event_name: str, *, session_id: str = HUB_ID):
        """
        Decorator to register a synchronous or asynchronous "lifecycle hook"
        (e.g. when a session registers/unregisters).

        Currently, hooks are stored internally and fired manually by register()/unregister().
        """

        def decorator(callback_fn: Any) -> Any:
            self._event_hooks.setdefault(event_name, []).append(callback_fn)
            return callback_fn

        return decorator

    async def _fire(self, event_name: str, *args: Any) -> None:
        """
        Invoke all registered lifecycle hooks for event_name, passing *args.

        Hooks may be synchronous or asynchronous. Synchronous hooks run in
        a background thread via asyncio.to_thread.
        """
        callbacks = self._event_hooks.get(event_name, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args)
                else:
                    # Run sync hook in a thread
                    await asyncio.to_thread(callback, *args)
            except Exception:
                log.exception(f"Event hook '{event_name}' raised an exception")

    ########### PUBLISH / REQUEST (Facade) ###########

    async def publish(self, *, message: QiMessage) -> None:
        """
        Fire‐and‐forget publish of a QiMessage (EVENT or REPLY).

        Args:
            message: QiMessage object
        """
        await self._bus.publish(message=message)

    async def request(
        self,
        *,
        topic: str,
        payload: dict[str, Any],
        context: dict[str, Any] | None = None,
        timeout: float | None = None,
        target: list[str] | None = None,
        parent_logical_id: str | None = None,
        session_id: str = HUB_ID,
    ) -> Any:
        """
        Send a REQUEST to the bus and await exactly one REPLY payload
        (or a TimeoutError).

        Args:
            topic:             the topic string
            payload:           dict of data
            context:           optional context
            timeout:           max seconds to wait for a reply
            target:            list of target logical_ids (or None for broadcast)
            parent_logical_id: optional parent logical_id (used if bubble=True)
            session_id:        the requester's logical ID

        Returns:
            The payload returned by the first handler that responded.

        Raises:
            asyncio.TimeoutError if no reply arrives within <timeout>
            RuntimeError        if too many pending requests exist for this session
        """
        return await self._bus.request(
            topic=topic,
            payload=payload,
            context=context,
            timeout=timeout,
            target=target,
            parent_logical_id=parent_logical_id,
            session_id=session_id,
        )

    ########### FALL THROUGH to the underlying bus for any other methods ###########

    def __getattr__(self, name: str) -> Any:
        """
        For any attribute not explicitly defined on QiHub, delegate to QiMessageBus.
        """
        if name.startswith("_"):
            raise AttributeError(f"'QiHub' object has no attribute '{name}'")
        return getattr(self._bus, name)


# Instantiate a single module‐level QiHub for convenience:
qi_hub: Final[QiHub] = QiHub()
