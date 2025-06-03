import asyncio
import inspect
import uuid
from collections import defaultdict
from typing import Any, Final

from core.bases.models import QiHandler, QiMessage, QiMessageType
from core.logger import get_logger

log = get_logger(__name__)


class QiHandlerRegistry:
    """
    Manages subscriptions of handler functions to specific message topics.

    This registry allows:
    - Registering multiple handlers for a single topic.
    - Dispatching incoming messages to all registered handlers for its topic.
    - Efficiently dropping all handlers associated with a specific session_id.

    Internal Structure:
        _by_topic: Maps topic (str) to a dict of {handler_id: QiHandler}.
        _by_session: Maps session_id (str) to a set of handler_ids registered by that session.
        _handler_to_topic: Maps handler_id (str) to its topic (str) for fast cleanup.
    All operations modifying the registry are protected by an asyncio.Lock.
    """

    def __init__(self) -> None:
        """Initializes the QiHandlerRegistry with empty structures and a new lock."""
        self._by_topic: defaultdict[str, dict[str, QiHandler]] = defaultdict(dict)
        self._by_session: defaultdict[str, set[str]] = defaultdict(set)
        self._handler_to_topic: dict[str, str] = {}  # Fast reverse lookup
        self._lock: Final = asyncio.Lock()  # Type hint for self._lock

    async def register(
        self, function: QiHandler, *, topic: str, session_id: str
    ) -> str:
        """
        Registers a handler function for a specific topic and associates it with a session.

        Args:
            function: The QiHandler (callable) to be registered.
            topic: The message topic to subscribe this handler to.
            session_id: The ID of the session registering this handler. Used for cleanup.

        Returns:
            A unique handler_id string for this registration, which can be used to
            unregister a specific handler if needed (though not directly implemented here).
        """
        handler_id = str(uuid.uuid4())
        async with self._lock:
            self._by_topic[topic][handler_id] = function
            self._by_session[session_id].add(handler_id)
            self._handler_to_topic[handler_id] = topic
        return handler_id

    async def dispatch(self, message: QiMessage) -> Any | None:
        """
        Dispatches an incoming message to all registered handlers for its topic.

        For messages of type REQUEST, it returns the result from the first handler
        that returns a non-None value. For other message types (e.g., EVENT),
        all handlers are executed, but their return values are not aggregated beyond logging.
        If multiple handlers exist, they are executed concurrently.
        Handler exceptions are caught and logged, not propagated.

        Args:
            message: The QiMessage object to dispatch.

        Returns:
            The result from a handler if it's a REQUEST message and a handler returns a value,
            otherwise None.
        """
        async with self._lock:
            # Operate on a copy to release lock quickly before handler execution
            functions = list(self._by_topic.get(message.topic, {}).values())

        if not functions:
            return None

        # Fast path: single handler (most common)
        if len(functions) == 1:
            try:
                handler = functions[0]
                if inspect.iscoroutinefunction(handler):
                    return await handler(message)
                else:
                    # Run synchronous handlers in a separate thread to avoid blocking asyncio loop
                    return await asyncio.to_thread(handler, message)
            except Exception as e:  # noqa: BLE001
                log.error(
                    f"Handler error for topic [{message.topic}] (single handler): {e}"
                )
                return None

        # Multiple handlers - execute all, gather results
        results = []
        # Execute all handlers concurrently
        tasks = []
        for handler in functions:
            if inspect.iscoroutinefunction(handler):
                tasks.append(handler(message))
            else:
                tasks.append(asyncio.to_thread(handler, message))

        # Gather results, logging errors for individual handlers
        # Using return_exceptions=True to ensure all handlers attempt to run
        gathered_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result_or_exc in enumerate(gathered_results):
            if isinstance(result_or_exc, Exception):
                log.error(
                    f"Handler error for topic [{message.topic}] (handler {i + 1}/{len(functions)}): {result_or_exc}"
                )
                results.append(None)  # Or some other error indicator if needed
            else:
                results.append(result_or_exc)

        # Return first non-None result for REQUEST type messages
        if message.type is QiMessageType.REQUEST:
            for result in results:
                if result is not None:
                    return result
        return None  # Or potentially a list of all results for EVENTs if that behavior is desired

    async def drop_session(self, session_id: str) -> None:
        """
        Removes all handlers associated with a given session_id.

        This is typically called when a session disconnects or is unregistered.
        It ensures that handlers from a defunct session do not attempt to process messages.

        Args:
            session_id: The ID of the session whose handlers should be dropped.
        """
        async with self._lock:
            handler_ids = self._by_session.pop(session_id, set())

            # O(h) cleanup using reverse lookup (h = number of handlers for this session)
            for handler_id in handler_ids:
                topic = self._handler_to_topic.pop(handler_id, None)
                if topic and topic in self._by_topic:
                    self._by_topic[topic].pop(handler_id, None)
                    # Remove topic from _by_topic if it no longer has any handlers
                    if not self._by_topic[topic]:
                        del self._by_topic[topic]
