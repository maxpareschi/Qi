# core/messaging/handlers.py

"""
This module contains the handler registry for the Qi system.
"""

import asyncio
from uuid import uuid4

from core.constants import HUB_ID
from core.logger import get_logger
from core.models import QiHandler

log = get_logger(__name__)


class QiHandlerRegistry:
    """
    Async-safe registry of handlers by topic and session_id.

        - Strong references to QiHandler objects
        - One handler_id per (function, topic, session) triplet
        - Multi-session support (the same function can be registered under multiple sessions)
        - Removal APIs:
            - drop_handler(handler_id)
            - drop_session(session_id)
        - Lookup:
            - get_handlers(topic, session_id) returns handlers in "two-tier" order
            (exact session_id first, then HUB_ID handlers)
    """

    def __init__(self) -> None:
        # handler_id → (topic, handler_fn)
        self._by_id: dict[str, QiHandler] = {}

        # topic → { handler_id → QiHandler }
        self._by_topic: dict[str, dict[str, QiHandler]] = {}

        # session_id → set of handler_ids that session has registered
        self._by_session: dict[str, set[str]] = {}

        # handler_id → topic (for efficient reverse lookup during cleanup)
        self._handler_id_to_topic: dict[str, str] = {}

        # lock for concurrent asyncio operations
        self._lock = asyncio.Lock()

    async def register(
        self, handler_function: QiHandler, *, topic: str, session_id: str
    ) -> str:
        """
        Register handler_fn for `topic` under `session_id`.
        Returns a unique handler_id (UUID string).

        We do NOT dedupe across sessions. If the same function+topic is registered
        twice under the _same_ session, that will produce two distinct handler_ids.

        Args:
            handler_fn:  a sync or async callable taking (QiMessage) → Any
            topic:       message topic string
            session_id:  logical ID of the session registering this handler

        Returns:
            handler_id (string)
        """
        async with self._lock:
            topic_dict = self._by_topic.setdefault(topic, {})

            new_handler_id = str(uuid4())
            new_handler = handler_function

            # Store in all indexes
            self._by_id[new_handler_id] = new_handler
            topic_dict[new_handler_id] = new_handler
            self._by_session.setdefault(session_id, set()).add(new_handler_id)
            self._handler_id_to_topic[new_handler_id] = topic

            if __debug__:
                self._assert_consistency()

            return new_handler_id

    async def drop_handler(self, *, handler_id: str) -> None:
        """
        Fully remove a single handler by its handler_id from all indexes.
        """
        async with self._lock:
            if handler_id not in self._by_id:
                return

            _ = self._by_id.pop(handler_id, None)
            topic = self._handler_id_to_topic.pop(handler_id, None)

            # Remove from by_topic
            if topic and topic in self._by_topic:
                topic_handlers = self._by_topic[topic]
                topic_handlers.pop(handler_id, None)
                if not topic_handlers:
                    self._by_topic.pop(topic, None)

            # Remove from by_session (reverse map)
            # A handler_id is unique per registration, so it will be in at most one session's set.
            for session_id, handler_ids_set in list(
                self._by_session.items()
            ):  # Use list for safe iteration if modifying
                if handler_id in handler_ids_set:
                    handler_ids_set.remove(handler_id)
                    if not handler_ids_set:
                        self._by_session.pop(session_id)
                    break  # Found and removed, no need to check other sessions

            if __debug__:
                self._assert_consistency()

    async def drop_session(self, *, session_id: str) -> None:
        """
        Detach all handlers registered by `session_id`.
        Any handler_id not present under another session is fully purged.

        Args:
            session_id: logical ID whose handlers should be removed
        """
        async with self._lock:
            handler_ids_to_remove = self._by_session.pop(session_id, set())
            for handler_id in handler_ids_to_remove:
                _ = self._by_id.pop(handler_id, None)  # Remove from main lookup
                topic = self._handler_id_to_topic.pop(
                    handler_id, None
                )  # Get topic and remove mapping

                if topic and topic in self._by_topic:
                    topic_handlers = self._by_topic[topic]
                    topic_handlers.pop(handler_id, None)
                    if not topic_handlers:  # If topic has no more handlers
                        self._by_topic.pop(topic)
            if __debug__:
                self._assert_consistency()

    async def get_handlers(self, *, topic: str, session_id: str) -> list[QiHandler]:
        """
        Return a list of handler functions for `topic`, in two tiers:
          1) Handlers registered under exactly this session_id
          2) Handlers registered under the "HUB" (session_id="__hub__")

        Args:
            topic:      the topic string to look up
            session_id: logical ID of the requesting session

        Returns:
            A list of callables (sync or async). If none found, returns an empty list.
        """
        handlers_to_call: list[QiHandler] = []
        seen_ids: set[str] = set()

        async with self._lock:
            topic_dict = self._by_topic.get(topic, {})

            # First pass: exact session_id
            for handler_id, handler_fn in topic_dict.items():
                if handler_id in self._by_session.get(session_id, set()):
                    handlers_to_call.append(handler_fn)
                    seen_ids.add(handler_id)

            # Second pass: HUB_ID sessions
            hub_handlers = self._by_session.get(HUB_ID, set())
            for handler_id, handler_fn in topic_dict.items():
                if handler_id not in seen_ids and handler_id in hub_handlers:
                    handlers_to_call.append(handler_fn)
                    seen_ids.add(handler_id)

        return handlers_to_call

    def _assert_consistency(self) -> None:
        """
        Debug assertion to validate forward/reverse mapping consistency.
        Ensures that every handler in _by_session appears in _by_topic/_by_id,
        and vice versa.
        """
        # Every handler_id in _by_session must be in _by_id and in _by_topic
        for session_id, handler_ids in self._by_session.items():
            for handler_id in handler_ids:
                assert handler_id in self._by_id, (
                    f"Handler {handler_id} in by_session[{session_id}] but not in _by_id"
                )
                assert handler_id in self._handler_id_to_topic, (
                    f"Handler {handler_id} in by_session[{session_id}] but not in _handler_id_to_topic"
                )
                topic_from_reverse_map = self._handler_id_to_topic[handler_id]
                assert topic_from_reverse_map in self._by_topic, (
                    f"Topic {topic_from_reverse_map} for handler {handler_id} not in _by_topic"
                )
                assert handler_id in self._by_topic[topic_from_reverse_map], (
                    f"Handler {handler_id} not in _by_topic[{topic_from_reverse_map}]"
                )

        # Every handler in _by_topic must appear in _by_id and in some _by_session and _handler_id_to_topic
        for topic, topic_dict in self._by_topic.items():
            for handler_id in topic_dict:
                assert handler_id in self._by_id, (
                    f"Handler {handler_id} in by_topic[{topic}] but not in _by_id"
                )
                assert handler_id in self._handler_id_to_topic, (
                    f"Handler {handler_id} in by_topic[{topic}] but not in _handler_id_to_topic"
                )
                assert self._handler_id_to_topic[handler_id] == topic, (
                    f"Handler {handler_id} in _by_topic[{topic}] but _handler_id_to_topic maps to {self._handler_id_to_topic[handler_id]}"
                )
                found_in_session = any(
                    handler_id in handler_ids
                    for handler_ids in self._by_session.values()
                )
                assert found_in_session, (
                    f"Handler {handler_id} in by_topic[{topic}] but not in any by_session"
                )

        # Every handler in _by_id must be in _by_topic, _by_session, and _handler_id_to_topic
        for handler_id in self._by_id:
            assert handler_id in self._handler_id_to_topic, (
                f"Handler {handler_id} in _by_id but not in _handler_id_to_topic"
            )
            topic_from_reverse_map = self._handler_id_to_topic[handler_id]
            assert (
                topic_from_reverse_map in self._by_topic
                and handler_id in self._by_topic[topic_from_reverse_map]
            ), (
                f"Handler {handler_id} in _by_id not found correctly in _by_topic via _handler_id_to_topic"
            )
            found_in_session = any(
                handler_id in handler_ids for handler_ids in self._by_session.values()
            )
            assert found_in_session, (
                f"Handler {handler_id} in _by_id but not in any by_session"
            )

        # Check consistency of _handler_id_to_topic with other maps
        for handler_id, topic in self._handler_id_to_topic.items():
            assert handler_id in self._by_id, (
                f"Handler {handler_id} in _handler_id_to_topic but not in _by_id"
            )
            assert topic in self._by_topic and handler_id in self._by_topic[topic], (
                f"Handler {handler_id} (topic: {topic}) in _handler_id_to_topic but not found in _by_topic"
            )
            found_in_session = any(
                handler_id in handler_ids for handler_ids in self._by_session.values()
            )
            assert found_in_session, (
                f"Handler {handler_id} in _handler_id_to_topic but not in any by_session"
            )

    async def clear(self) -> None:
        """
        Purge every handler and every session mapping.
        """
        async with self._lock:
            self._by_id.clear()
            self._by_topic.clear()
            self._by_session.clear()
            self._handler_id_to_topic.clear()

            if __debug__:
                self._assert_consistency()
