from __future__ import annotations

import asyncio
from typing import Any, Final

from fastapi import WebSocket

from core.bases.models import QiCallback, QiMessage, QiSession
from core.logger import get_logger
from core.network.message_bus import QiMessageBus

log = get_logger(__name__)


class QiHub:
    """
    Public facade for interacting with the Qi messaging system.

    This class provides a simplified interface for common operations like registering
    sessions, publishing messages, making requests, and subscribing to topics.
    It also allows for registering event hooks for specific lifecycle events (e.g., session registration).

    Most of its messaging functionalities are delegated to an internal QiMessageBus instance.
    A global instance of this class (`hub`) is provided for easy access throughout an application.
    """

    def __init__(self) -> None:
        """Initializes the QiHub with a new QiMessageBus and an empty hooks dictionary."""
        self._bus = QiMessageBus()
        self._hooks: dict[str, list[QiCallback]] = {}

    def on_event(self, name: str):
        """
        Decorator to register a callback function for a specific hub event.

        Example:
            @hub.on_event("register")
            async def my_on_register_callback(session_info: QiSession):
                log.info(f"Session registered: {session_info.logical_id}")

        Args:
            name: The name of the event to subscribe to (e.g., "register", "unregister", "publish").

        Returns:
            A decorator function that registers the decorated callback.
        """

        def _decorator(callback: QiCallback):
            """Registers the provided callback for the specified event name."""
            self._hooks.setdefault(name, []).append(callback)
            return callback

        return _decorator

    async def _fire(self, name: str, *args, run_hooks: bool = False) -> None:
        """
        Internal method to execute all registered callback hooks for a given event name.

        Callbacks can be synchronous or asynchronous. Synchronous callbacks are run
        in a separate thread to avoid blocking the asyncio loop.
        Exceptions raised by hooks are caught and logged.

        Args:
            name: The name of the event whose hooks should be fired.
            *args: Positional arguments to pass to the callback hooks.
            run_hooks: If False, this method does nothing. Defaults to False.
                     This flag must be explicitly passed as True by public methods to run hooks.
        """
        if not run_hooks or name not in self._hooks:
            return

        for callback in self._hooks[name]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args)
                else:
                    await asyncio.to_thread(callback, *args)
            except Exception as e:  # noqa: BLE001
                log.error(f"Hook for event '{name}' failed: {e}")

    async def register(
        self, socket: WebSocket, info: QiSession, *, run_hooks: bool = False
    ) -> None:
        """
        Registers a WebSocket connection and session with the message bus.
        Optionally fires "register" event hooks.

        Args:
            socket: The WebSocket connection object.
            info: The QiSession information for this connection.
            run_hooks: If True, fires "register" event hooks. Defaults to False.
        """
        await self._bus.register(socket, info)
        # Pass the QiSession info to the hook
        await self._fire("register", info, run_hooks=run_hooks)

    async def unregister(self, session_id: str, *, run_hooks: bool = False) -> None:
        """
        Unregisters a session from the message bus by its session ID.
        Optionally fires "unregister" event hooks.

        Args:
            session_id: The ID of the session to unregister.
            run_hooks: If True, fires "unregister" event hooks. Defaults to False.
        """
        await self._bus.unregister(session_id)
        # Pass the session_id to the hook
        await self._fire("unregister", session_id, run_hooks=run_hooks)

    async def publish(self, message: QiMessage, *, run_hooks: bool = False) -> None:
        """
        Publishes a message to the message bus.
        Optionally fires "publish" event hooks.

        Args:
            message: The QiMessage to publish.
            run_hooks: If True, fires "publish" event hooks. Defaults to False.
        """
        await self._bus.publish(message)
        await self._fire("publish", message, run_hooks=run_hooks)

    async def request(self, *args, **kwargs) -> Any:
        """
        Sends a request message via the message bus and awaits a reply.

        This method delegates directly to the `request` method of the internal QiMessageBus.
        Refer to `QiMessageBus.request` for detailed arguments and behavior.

        Returns:
            The payload of the reply message.

        Raises:
            TimeoutError: If no reply is received within the specified timeout.
            ValueError: If timeout arguments are invalid.
        """
        return await self._bus.request(*args, **kwargs)

    def on(self, topic: str, *, session_id: str = "__hub__"):
        """
        Decorator to register a message handler for a specific topic.

        This method delegates directly to the `on` method of the internal QiMessageBus.
        Handlers registered via `hub.on()` are associated with a special "__hub__" session_id
        by default, meaning they are not tied to a specific client session lifecycle unless
        a different `session_id` is provided.

        Args:
            topic: The message topic to subscribe the handler to.
            session_id: The session ID to associate with this handler. Defaults to "__hub__".

        Returns:
            A decorator function for registering the QiHandler.
        """
        return self._bus.on(topic, session_id=session_id)

    def __getattr__(self, item: str) -> Any:
        """
        Fallback attribute access to the internal QiMessageBus instance.

        This allows QiHub to expose any additional helper methods or attributes
        of QiMessageBus without needing to explicitly redefine them in QiHub.

        Args:
            item: The name of the attribute being accessed.

        Returns:
            The attribute from the internal QiMessageBus instance.

        Raises:
            AttributeError: If the attribute is not found on the QiMessageBus.
        """
        return getattr(self._bus, item)


hub: Final = QiHub()
"""Global singleton instance of the QiHub, providing easy access to messaging functions."""
