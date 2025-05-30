# core/bus/handler.py

import asyncio
import weakref
from collections.abc import Awaitable
from typing import TypeAlias
from uuid import uuid4

from core.bases import Handler, QiHandler, QiMessage
from core.logger import get_logger

log = get_logger(__name__)


SlotRef: TypeAlias = weakref.ReferenceType[Handler] | Handler


class QiHandlerManager:
    """
    Registry for QiHandler by topic and by ID, with optional weak-reference support,
    built-in async/sync dispatch, and automatic pruning of dead handlers.
    """

    def __init__(self, use_weakrefs: bool = False):
        """
        Initialize a new QiHandlerManager.

        Args:
            use_weakrefs (bool): Whether to use weak references for handlers.
        """

        # handler_id → QiHandler
        self.by_id: dict[str, QiHandler] = {}

        # topic → list of handler_ids
        self.by_topic: dict[str, list[str]] = {}

        # handler_id → slot ref (WeakMethod/ref or strong Handler)
        self._slots: dict[str, SlotRef] = {}
        self.use_weakrefs = use_weakrefs

        # lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def register(self, handler_fn: Handler, topic: str, priority: int = 0) -> str:
        """
        Subscribe `handler_fn` to `topic` with given `priority`.
        Returns the new handler's unique ID.
        """
        # Before adding, prune any dead handlers on this topic
        await self._prune_dead_for_topic(topic)

        hndl_id = str(uuid4())
        qi_handler = QiHandler(
            id=hndl_id, topic=topic, priority=priority, handler=handler_fn
        )

        # Build slot_ref
        if self.use_weakrefs and hasattr(handler_fn, "__self__"):
            slot_ref: SlotRef = weakref.WeakMethod(handler_fn)
        elif self.use_weakrefs:
            try:
                slot_ref = weakref.ref(handler_fn)  # type: ignore
            except TypeError:
                slot_ref = handler_fn
        else:
            slot_ref = handler_fn

        async with self._lock:
            self.by_id[hndl_id] = qi_handler
            self.by_topic.setdefault(topic, []).append(hndl_id)
            self._slots[hndl_id] = slot_ref

        return hndl_id

    async def unregister(
        self,
        *,
        handler_id: str | None = None,
        handler_fn: Handler | None = None,
        topic: str | None = None,
    ) -> None:
        """
        Unsubscribe handlers by `handler_id` or by the function `handler_fn`.
        If `topic` is provided with no other args, clears all handlers on that topic.
        Removes entries from by_id, by_topic, and _slots.
        """
        async with self._lock:
            # If only topic is provided, clear it entirely
            if topic and not handler_id and not handler_fn:
                for hndl_id in self.by_topic.get(topic, []):
                    self.by_id.pop(hndl_id, None)
                    self._slots.pop(hndl_id, None)
                self.by_topic.pop(topic, None)
                return

            # Build set of targets to remove
            targets: set[str] = set()
            if handler_id:
                targets.add(handler_id)
            if handler_fn:
                for hndl_id, slot_ref in self._slots.items():
                    fn = (
                        slot_ref()
                        if isinstance(slot_ref, weakref.ReferenceType)
                        else slot_ref
                    )
                    if fn == handler_fn:
                        targets.add(hndl_id)

            # Remove matches
            for hndl_id in targets:
                hndl = self.by_id.pop(hndl_id, None)
                self._slots.pop(hndl_id, None)
                if not hndl:
                    continue
                lst = self.by_topic.get(hndl.topic, [])
                if hndl_id in lst:
                    lst.remove(hndl_id)
                    if lst:
                        self.by_topic[hndl.topic] = lst
                    else:
                        self.by_topic.pop(hndl.topic, None)

    async def dispatch(self, message: QiMessage) -> None:
        """
        Deliver `message` to all handlers for its topic, sorted by descending priority.
        Automatically prunes dead weakrefs and logs handler exceptions.
        """
        async with self._lock:
            handler_ids = list(self.by_topic.get(message.topic, []))

        # Gather live handlers and sort
        handlers = [
            self.by_id[hndl_id] for hndl_id in handler_ids if hndl_id in self.by_id
        ]
        handlers.sort(key=lambda h: h.priority, reverse=True)

        for hndl in handlers:
            slot_ref = self._slots.get(hndl.id)
            if isinstance(slot_ref, weakref.ReferenceType):
                fn = slot_ref()
            else:
                fn = slot_ref

            if fn is None:
                # stale weakref → unregister
                await self.unregister(handler_id=hndl.id)
                continue

            try:
                result = fn(message)
                if isinstance(result, Awaitable):
                    await result
            except Exception:
                log.exception(f"Error in handler {hndl.id} for topic {hndl.topic}")

    async def clear(self) -> None:
        """Remove all subscriptions."""
        async with self._lock:
            self.by_id.clear()
            self.by_topic.clear()
            self._slots.clear()

    async def _prune_dead_for_topic(self, topic: str) -> None:
        """
        Remove any handlers on `topic` whose weakrefs have gone stale.
        """
        async with self._lock:
            for hndl_id in list(self.by_topic.get(topic, [])):
                slot_ref = self._slots.get(hndl_id)
                if isinstance(slot_ref, weakref.ReferenceType) and slot_ref() is None:
                    # remove stale
                    self.by_id.pop(hndl_id, None)
                    self.by_topic[topic].remove(hndl_id)
                    self._slots.pop(hndl_id, None)
            # if topic empty, drop it
            if not self.by_topic.get(topic):
                self.by_topic.pop(topic, None)
