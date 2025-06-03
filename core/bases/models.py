from __future__ import annotations

import time
from enum import Enum
from typing import Any, Awaitable, Callable, List, Tuple, TypeAlias
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

TupleKey2: TypeAlias = Tuple[str | None, str | None]
TupleKey3: TypeAlias = Tuple[str | None, str | None, str | None]


class QiMessageType(str, Enum):
    """Enumeration of Qi message types."""

    EVENT = "event"
    REQUEST = "request"
    REPLY = "reply"


class QiUser(BaseModel):
    """Represents a user in the Qi system."""

    id: str | None = None
    name: str | None = None
    email: str | None = None

    @property
    def key(self) -> TupleKey2:
        """Generates a unique tuple key for the user based on id and name."""
        return (self.id, self.name)


class QiContext(BaseModel):
    """Represents the contextual information for a Qi message or operation."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    project: str | None = None
    entity: str | None = None
    task: str | None = None

    @property
    def key(self) -> TupleKey3:
        """Generates a unique tuple key for the context based on project, entity, and task."""
        return (self.project, self.entity, self.task)


class QiSession(BaseModel):
    """
    Represents a client session connected to the Qi system.
    Each session has a unique id and a user-defined logical_id.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    logical_id: str
    parent_logical_id: str | None = None
    tags: List[str] = Field(default_factory=list)

    @field_validator("logical_id")
    @classmethod
    def _validate_logical_id(cls, value: str) -> str:
        """Validates that logical_id is between 1 and 100 characters."""
        if not value or len(value) > 100:
            raise ValueError("logical_id must be 1-100 characters")
        return value


class QiMessage(BaseModel):
    """
    Represents a generic message exchanged within the Qi system.
    Key attributes include topic, type, sender, payload, and context.
    """

    message_id: str = Field(default_factory=lambda: str(uuid4()))
    topic: str
    type: QiMessageType
    sender: QiSession
    target: List[str] = Field(default_factory=list)
    reply_to: str | None = None
    context: QiContext | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=lambda: time.time())
    bubble: bool = False  # route to parent if True

    @field_validator("topic")
    @classmethod
    def _no_wildcards(cls, value: str) -> str:
        """Validates topic constraints: 1-200 chars, no wildcards."""
        if not value or len(value) > 200:
            raise ValueError("topic must be 1-200 characters")
        if "*" in value or ">" in value:
            raise ValueError("wildcards are disallowed")
        return value

    @field_validator("target")
    @classmethod
    def _validate_target(cls, value: list[str]) -> list[str]:
        """Validates that the target list does not exceed 50 recipients."""
        if len(value) > 50:  # Prevent broadcast storms
            raise ValueError("target list cannot exceed 50 recipients")
        return value

    @field_validator("payload")
    @classmethod
    def _validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Validates that the payload does not have an excessive number of top-level keys."""
        if len(value) > 100:  # Reasonable number of top-level keys
            raise ValueError("payload has too many top-level keys (max 100)")
        return value


QiCallback: TypeAlias = Callable[..., Any]
"""Type alias for a generic callback function used in event handling or hooks."""

QiHandler: TypeAlias = Callable[[QiMessage], Awaitable[Any] | Any]
"""Type alias for a Qi message handler function. Can be sync or async."""
