from collections import defaultdict
from dataclasses import (
    field,
    # dataclass,
)
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic.dataclasses import dataclass


@dataclass
class QiMessageContext:
    """Context for a message."""

    project: str | None = None
    entity: str | None = None
    task: str | None = None


@dataclass
class QiMessageUser:
    """User information for a message."""

    user_id: str | None = None
    user_name: str | None = None
    user_email: str | None = None
    # Future fields: auth tokens, permissions, roles, etc.


@dataclass
class QiMessageSource:
    """Source info for a message."""

    addon: str = "core"
    session_id: str = field(default_factory=lambda: str(uuid4()))
    window_id: str | None = None
    user: QiMessageUser | None = None


@dataclass
class QiMessage:
    """A message in the Qi system."""

    message_id: str = field(default_factory=lambda: str(uuid4()))
    topic: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    source: QiMessageSource | None = None
    data: dict[str, Any] | None = None
    context: QiMessageContext | None = None
    user: QiMessageUser | None = None
    reply_to: str | None = None


@dataclass
class QiMessageManager:
    """Registry for messages.
    This class is used to store messages sent between the Qi managed processes.
    It mantains an index of messages by ID, topic, source and reply_to in its
    internal dictionaries.
    """

    by_id: defaultdict[str, QiMessage] = field(
        default_factory=lambda: defaultdict(QiMessage)
    )
    by_topic: defaultdict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    by_source: defaultdict[tuple[str, str, str | None], list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    by_addon: defaultdict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    by_session: defaultdict[tuple[str, str], list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    by_window: defaultdict[tuple[str, str | None], list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    by_reply_to: defaultdict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def register(self, message: QiMessage) -> None:
        """Store a message and index it by topic, source and reply_to."""

        self.by_id[message.message_id] = message
        self.by_topic[message.topic].append(message.message_id)

        if message.source:
            key = (
                message.source.addon,
                message.source.session_id,
                message.source.window_id,
            )
            self.by_source[key].append(message.message_id)
            self.by_addon[message.source.addon].append(message.message_id)
            self.by_session[message.source.session_id].append(message.message_id)
            self.by_window[message.source.window_id].append(message.message_id)

        if message.reply_to:
            self.by_reply_to[message.reply_to].append(message.message_id)

    def unregister(
        self, message: QiMessage | None = None, message_id: str | None = None
    ) -> None:
        """Remove a message (and all index entries pointing to it)."""

        if message is not None:
            message = self.by_id.pop(message.message_id, None)
        elif message_id is not None:
            message = self.by_id.pop(message_id, None)
        if message is None:
            return

        self.by_topic[message.topic] = list(
            filter(
                lambda message_id: message_id != message.message_id,
                self.by_topic[message.topic],
            )
        )
        if self.by_topic.get(message.topic, None) is None:
            self.by_topic.pop(message.topic, None)

        source_key = (
            message.source.addon,
            message.source.session_id,
            message.source.window_id,
        )
        self.by_source[source_key] = list(
            filter(
                lambda message_id: message_id != message.message_id,
                self.by_source[source_key],
            )
        )
        if self.by_source.get(source_key, None) is None:
            self.by_source.pop(source_key, None)

        self.by_addon[message.source.addon] = list(
            filter(
                lambda message_id: message_id != message.message_id,
                self.by_addon[message.source.addon],
            )
        )
        if self.by_addon.get(message.source.addon, None) is None:
            self.by_addon.pop(message.source.addon, None)

        self.by_session[message.source.session_id] = list(
            filter(
                lambda message_id: message_id != message.message_id,
                self.by_session[message.source.session_id],
            )
        )
        if self.by_session.get(message.source.session_id, None) is None:
            self.by_session.pop(message.source.session_id, None)

        self.by_window[message.source.window_id] = list(
            filter(
                lambda message_id: message_id != message.message_id,
                self.by_window[message.source.window_id],
            )
        )
        if self.by_window.get(message.source.window_id, None) is None:
            self.by_window.pop(message.source.window_id, None)

        self.by_reply_to[message.reply_to] = list(
            filter(
                lambda message_id: message_id != message.message_id,
                self.by_reply_to[message.reply_to],
            )
        )
        if self.by_reply_to.get(message.reply_to, None) is None:
            self.by_reply_to.pop(message.reply_to, None)

    def clear(self) -> None:
        """Wipe every message and index."""

        self.by_id.clear()
        self.by_topic.clear()
        self.by_source.clear()
        self.by_reply_to.clear()

    def get_by_id(self, message_id: str) -> QiMessage | None:
        """Return a message by its ID."""

        return self.by_id.get(message_id)

    def get_by_topic(self, topic: str) -> list[QiMessage]:
        """Return all messages for a topic, in insertion order."""

        return [self.by_id[msgid] for msgid in self.by_topic.get(topic, [])]

    def get_by_source(self, source: QiMessageSource) -> list[QiMessage]:
        """Return all messages for a source, in insertion order."""

        key = (source.addon, source.session_id, source.window_id)
        return [self.by_id[msg_id] for msg_id in self.by_source.get(key, [])]

    def get_by_addon(self, addon: str) -> list[QiMessage]:
        """Return all messages for an addon, in insertion order."""

        return [self.by_id[msg_id] for msg_id in self.by_addon.get(addon, [])]

    def get_by_session(self, session_id: str) -> list[QiMessage]:
        """Return all messages for a session, in insertion order."""

        return [self.by_id[msg_id] for msg_id in self.by_session.get(session_id, [])]

    def get_by_window(self, window_id: str) -> list[QiMessage]:
        """Return all messages for a window, in insertion order."""

        return [self.by_id[msg_id] for msg_id in self.by_window.get(window_id, [])]

    def get_by_reply_to(
        self, reply: QiMessage | None = None, reply_id: str | None = None
    ) -> list[QiMessage]:
        """Return all messages for a reply, in insertion order."""

        if reply_id is not None and reply is None:
            reply = self.by_id.get(reply_id)
        if reply is None:
            return []
        return [
            self.by_id[msg_id] for msg_id in self.by_reply_to.get(reply.message_id, [])
        ]

    def get_by_order(self, reverse: bool = False) -> list[QiMessage]:
        """Return all messages in insertion order."""

        return sorted(
            self.by_id.values(), key=lambda message: message.timestamp, reverse=reverse
        )
