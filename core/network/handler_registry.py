import asyncio
import inspect
import uuid
from collections import defaultdict
from typing import Any

from core.bases.models import QiHandler, QiMessage, QiMessageType
from core.logger import get_logger

log = get_logger(__name__)


class QiHandlerRegistry:
    """
    topic → {handler_id: function}
    session_id → {handler_id}
    handler_id → topic (for O(1) cleanup)
    """

    def __init__(self) -> None:
        self._by_topic: defaultdict[str, dict[str, QiHandler]] = defaultdict(dict)
        self._by_session: defaultdict[str, set[str]] = defaultdict(set)
        self._handler_to_topic: dict[str, str] = {}  # Fast reverse lookup
        self._lock = asyncio.Lock()

    async def register(
        self, function: QiHandler, *, topic: str, session_id: str
    ) -> str:
        handler_id = str(uuid.uuid4())
        async with self._lock:
            self._by_topic[topic][handler_id] = function
            self._by_session[session_id].add(handler_id)
            self._handler_to_topic[handler_id] = topic
        return handler_id

    async def dispatch(self, message: QiMessage) -> Any | None:
        """Execute handlers - optimized for single handler case"""
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
                    return await asyncio.to_thread(handler, message)
            except Exception as e:  # noqa: BLE001
                log.error(f"Handler error [{message.topic}]: {e}")
                return None

        # Multiple handlers - execute all, return first result
        results = []
        for handler in functions:
            try:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(message)
                else:
                    result = await asyncio.to_thread(handler, message)
                results.append(result)
            except Exception as e:  # noqa: BLE001
                log.error(f"Handler error [{message.topic}]: {e}")
                results.append(None)

        # Return first non-None result for REQUEST
        if message.type is QiMessageType.REQUEST:
            for result in results:
                if result is not None:
                    return result
        return None

    async def drop_session(self, session_id: str) -> None:
        async with self._lock:
            handler_ids = self._by_session.pop(session_id, set())

            # O(h) cleanup using reverse lookup
            for handler_id in handler_ids:
                topic = self._handler_to_topic.pop(handler_id, None)
                if topic and topic in self._by_topic:
                    self._by_topic[topic].pop(handler_id, None)
                    # Remove empty topics
                    if not self._by_topic[topic]:
                        del self._by_topic[topic]
