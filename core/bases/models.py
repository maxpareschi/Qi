# core/bases/models.py
"""
Common models for the Qi platform.
This module contains the core models for the Qi platform.
The models are designed as dataclasses, but actual decorator
will be applied in the 'core.config' module through monkey-patching.

In Development (QI_DEV=True):
    The models will get decorated using pydantic 'dataclass' decorator.
In Production (QI_DEV=False):
    The models will get decorated using the 'dataclass' decorator.

This is to ensure that the models are validated in development,
but not in production, to avoid performance issues.
the core.config module will also have a dataclass and a field import
for convenience, to let the developer choose between relying on
background monkey-patching or doing it manually.

"""

from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, TypeAlias
from uuid import uuid4

from fastapi import WebSocket

from core import dataclass, field
from core.logger import get_logger

log = get_logger(__name__)


class QiMessageType(str, Enum):
    NORMAL = "normal"
    TRANSIENT = "transient"
    ACK = "ack"
    CACHE_ONLY = "cache"
    STATEFUL = "stateful"


SourceKey: TypeAlias = tuple[str, str, str | None]
OptionalKey: TypeAlias = tuple[str | None, str | None, str | None]


@dataclass
class QiUser:
    """User metadata."""

    id: str | None = None
    name: str | None = None
    email: str | None = None

    @property
    def key(self) -> OptionalKey:
        return (self.id, self.name, self.email)


@dataclass
class QiContext:
    """Contextual metadata for tasks, projects, etc."""

    id: str = field(default_factory=lambda: str(uuid4()))
    project: str | None = None
    entity: str | None = None
    task: str | None = None

    @property
    def key(self) -> OptionalKey:
        return (self.project, self.entity, self.task)


@dataclass
class QiSource:
    """Generic source object for messages, connections, etc."""

    id: str = field(default_factory=lambda: str(uuid4()))
    addon: str
    session_id: str
    window_id: str | None = None

    @property
    def key(self) -> SourceKey:
        return (self.addon, self.session_id, self.window_id)


@dataclass
class QiMessage:
    """A message to be sent through the message bus."""

    id: str = field(default_factory=lambda: str(uuid4()))
    topic: str
    type: QiMessageType = QiMessageType.NORMAL
    requires_ack: bool = False

    # TODO: take this out at some point since it's redundant.
    # QiMessageType.ACK already hints at id being the reply target,
    # so reply_to is more of a convenience field for now.
    reply_to: str | None = None

    # TODO: take this out at some point since it could make sense to
    # just specify an expiration per QiMessageType by default.
    expires_at: float | None = None

    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    source: QiSource | None = None
    data: dict[str, Any] | None = None
    context: QiContext | None = None
    user: QiUser | None = None


@dataclass
class QiConnection:
    """A connection to the message bus."""

    id: str = field(default_factory=lambda: str(uuid4()))
    socket: WebSocket
    source: QiSource


Handler: TypeAlias = Callable[[QiMessage], Any | Awaitable[Any]]


@dataclass
class QiHandler:
    """A single handler subscription."""

    id: str
    handler: Handler
    topic: str
