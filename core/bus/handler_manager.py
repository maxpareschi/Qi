# core/bus/handler.py

import asyncio
from uuid import uuid4

from core.bases.models import Handler, QiHandler, QiSource, SourceKey
from core.logger import get_logger

log = get_logger(__name__)


class QiHandlerManager:
    """
    Async-safe registry of handlers by topic and QiSource.key,

    • Strong refs only
    • Dedupe identical (fn, topic)
    • Multi-source support
    • Two removal APIs:
        - remove_handler(handler_id)
        - remove_handlers_for_source(source)
    • Two-tier lookup: exact window → session
    """

    def __init__(self) -> None:
        """
        Initialize a new handler manager.
        """

        # handler_id → QiHandler
        self.by_id: dict[str, QiHandler] = {}

        # topic → { handler_id → QiHandler }
        self.by_topic: dict[str, dict[str, QiHandler]] = {}

        # source_key → set of handler_ids
        self.by_source: dict[SourceKey, set[str]] = {}

        # reverse mapping: handler_id → set of source_keys (for efficient removal)
        self.handler_to_sources: dict[str, set[SourceKey]] = {}

        # lock for concurrent asyncio operations
        self._lock = asyncio.Lock()

    async def register(
        self, handler_fn: Handler, *, topic: str, source: QiSource
    ) -> str:
        """
        Register handler_fn for topic under source.key.
        Reuses existing handler_id if (fn,topic) already seen,
        and ensures by_source[source.key] contains that ID.
        """

        async with self._lock:
            topic_dict = self.by_topic.setdefault(topic, {})

            # 1) Dedupe: same fn+topic?
            for _handler_id, _handler in topic_dict.items():
                if _handler.handler is handler_fn:
                    self.by_source.setdefault(source.key, set()).add(_handler_id)
                    self.handler_to_sources.setdefault(_handler_id, set()).add(
                        source.key
                    )
                    # Debug consistency check
                    if __debug__:
                        self._assert_consistency()
                    return _handler_id

            # 2) Brand-new handler
            _handler_id = str(uuid4())
            _handler = QiHandler(id=_handler_id, topic=topic, handler=handler_fn)

            self.by_id[_handler_id] = _handler
            topic_dict[_handler_id] = _handler
            self.by_source.setdefault(source.key, set()).add(_handler_id)
            self.handler_to_sources[_handler_id] = {source.key}

            # Debug consistency check
            if __debug__:
                self._assert_consistency()

            return _handler_id

    def _purge_handler(self, handler_id: str) -> None:
        """
        Internal helper to remove handler from by_id and by_topic indexes.
        Must be called with lock held.
        """

        _handler = self.by_id.pop(handler_id, None)
        if not _handler:
            return

        # remove from by_topic
        topic_dict = self.by_topic.get(_handler.topic, {})
        topic_dict.pop(handler_id, None)
        if not topic_dict:
            self.by_topic.pop(_handler.topic, None)

    async def remove_by_id(self, *, handler_id: str) -> None:
        """
        Fully remove a single handler (by ID) from all indexes.
        """

        async with self._lock:
            # Check if handler exists before proceeding
            if handler_id not in self.by_id:
                return

            # remove from by_source using reverse mapping (more efficient)
            source_keys = self.handler_to_sources.pop(handler_id, set())
            for source_key in source_keys:
                _handler_ids = self.by_source.get(source_key)
                if _handler_ids:
                    _handler_ids.discard(handler_id)
                    if not _handler_ids:
                        self.by_source.pop(source_key)

            # purge from by_id and by_topic (includes consistency check)
            self._purge_handler(handler_id)

            # Debug consistency check
            if __debug__:
                self._assert_consistency()

    async def remove_by_source(self, *, source: QiSource) -> None:
        """
        Detach all handlers under this source.key.
        Any handler_id not present under another source is fully removed.
        """

        async with self._lock:
            _handler_ids = self.by_source.pop(source.key, set())
            for _handler_id in _handler_ids:
                # Get reverse-map entry (don't pop yet)
                handler_sources = self.handler_to_sources.get(_handler_id)
                if handler_sources is None:
                    log.warning(
                        f"Handler {_handler_id!r} in by_source but missing in reverse map"
                    )
                    continue

                # Remove this source from the set
                handler_sources.discard(source.key)

                if handler_sources:
                    # Still has other sources, leave mapping alone
                    pass
                else:
                    # No more sources: pop from reverse map and purge
                    self.handler_to_sources.pop(_handler_id, None)
                    self._purge_handler(_handler_id)

            # Debug consistency check
            if __debug__:
                self._assert_consistency()

    async def get_handlers(self, *, topic: str, source: QiSource) -> list[QiHandler]:
        """
        Return handlers for `topic` in two tiers:
          1) exact window:    (addon,session,window)
          2) session-only:     (addon,session,None)
        """

        addon, session, window = source.key
        keys: list[SourceKey] = []
        if window is not None:
            keys.append((addon, session, window))
        # Only add session-only key if it's different from window key
        session_key = (addon, session, None)
        if session_key not in keys:
            keys.append(session_key)

        out: list[QiHandler] = []
        seen: set[str] = set()

        async with self._lock:
            for key in keys:
                for _handler_id in self.by_source.get(key, set()):
                    if _handler_id not in seen:
                        seen.add(_handler_id)
                        _handler = self.by_id.get(_handler_id)
                        if _handler and _handler.topic == topic:
                            out.append(_handler)

        return out

    async def clear_by_topic(self, *, topic: str) -> None:
        """
        Remove all handlers for a specific topic, across all sources.
        """

        async with self._lock:
            # Grab and drop the topic map in one go
            handler_ids = list(self.by_topic.pop(topic, {}))

            for _handler_id in handler_ids:
                # Detach from all sources using reverse mapping
                for source_key in self.handler_to_sources.pop(_handler_id, set()):
                    _handler_ids = self.by_source.get(source_key)
                    if _handler_ids:
                        _handler_ids.discard(_handler_id)
                        if not _handler_ids:
                            self.by_source.pop(source_key)

                # Use _purge_handler for consistent removal (handles by_id cleanup + validation)
                self._purge_handler(_handler_id)

            if __debug__:
                self._assert_consistency()

    # Introspection helpers for debugging/testing
    def topics(self) -> list[str]:
        """Return list of all registered topics."""

        return list(self.by_topic.keys())

    def sources(self) -> list[SourceKey]:
        """Return list of all source keys with handlers."""

        return list(self.by_source.keys())

    def scopes_for(self, handler_id: str) -> set[SourceKey]:
        """Return set of source keys for a given handler."""

        return self.handler_to_sources.get(handler_id, set()).copy()

    def _assert_consistency(self) -> None:
        """
        Debug assertion to validate forward/reverse mapping consistency.
        Call in tests to catch any drift between indexes.
        """

        # Check: every handler in handler_to_sources exists in other indexes
        for handler_id, source_keys in self.handler_to_sources.items():
            assert handler_id in self.by_id, (
                f"Handler {handler_id} in reverse map but not in by_id"
            )
            handler = self.by_id[handler_id]
            assert handler_id in self.by_topic.get(handler.topic, {}), (
                f"Handler {handler_id} missing from by_topic"
            )

            for source_key in source_keys:
                assert handler_id in self.by_source.get(source_key, set()), (
                    f"Handler {handler_id} missing from by_source[{source_key}]"
                )

        # Check: every handler in by_source appears in reverse map
        for source_key, handler_ids in self.by_source.items():
            for handler_id in handler_ids:
                assert source_key in self.handler_to_sources.get(handler_id, set()), (
                    f"Source {source_key} missing from reverse map for handler {handler_id}"
                )

        # Check: no empty sets in any mapping
        assert all(handler_ids for handler_ids in self.by_source.values()), (
            "Empty set found in by_source"
        )
        assert all(source_keys for source_keys in self.handler_to_sources.values()), (
            "Empty set found in handler_to_sources"
        )

    async def clear(self) -> None:
        """Purge every handler and every source mapping."""

        async with self._lock:
            self.by_id.clear()
            self.by_topic.clear()
            self.by_source.clear()
            self.handler_to_sources.clear()

            if __debug__:
                self._assert_consistency()
