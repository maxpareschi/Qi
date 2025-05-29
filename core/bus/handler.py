from collections import defaultdict
from dataclasses import (
    field,
    # dataclass,
)
from typing import Any, Awaitable, Callable, TypeAlias
from uuid import uuid4

from pydantic.dataclasses import dataclass

from core.bus.message import QiMessage

Handler: TypeAlias = Callable[[QiMessage], Any | Awaitable[Any]]


@dataclass
class QiHandler:
    """A handler for a topic."""

    handler_id: str = field(default_factory=lambda: str(uuid4()))
    handler: Handler
    topic: str
    priority: int = 0


@dataclass
class QiHandlerManager:
    """Registry for handlers for a topic.
    This class is used to store handlers for a topic.
    It mantains an index of handlers for a topic in its internal dictionary.
    """

    by_id: defaultdict[str, QiHandler] = field(
        default_factory=lambda: defaultdict(QiHandler)
    )

    by_topic: defaultdict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def register(self, handler: Handler, topic: str, priority: int = 0) -> None:
        """Register a handler for a topic."""

        self.by_topic[topic].append(QiHandler(handler, topic, priority))

    def unregister(self, handler: Handler, topic: str) -> None:
        """Unregister a handler for a topic."""

        for hndl in self.get_by_topic(topic):
            if hndl.handler == handler:
                self.by_topic[topic].remove(hndl)
                if not self.by_topic[topic]:
                    self.by_topic.pop(topic, None)

    def get_by_id(self, handler_id: str) -> QiHandler | None:
        """Return all handlers for a handler ID."""

        return self.by_id.get(handler_id, None)

    def get_by_topic(self, topic: str) -> list[QiHandler]:
        """Return all handlers for a topic."""

        result = []
        handler_ids = self.by_topic.get(topic, [])
        for handler_id in handler_ids:
            handler = self.get_by_id(handler_id)
            if handler:
                result.append(handler)
        return result

    def clear(self) -> None:
        """Clear all handlers."""

        self.by_id.clear()
        self.by_topic.clear()
