from __future__ import annotations

import time
from asyncio import Future
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, List, Tuple, TypeAlias
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

TupleKey2: TypeAlias = Tuple[str | None, str | None]
TupleKey3: TypeAlias = Tuple[str | None, str | None, str | None]


class QiMessageType(str, Enum):
    EVENT = "event"
    REQUEST = "request"
    REPLY = "reply"


class QiUser(BaseModel):
    id: str | None = None
    name: str | None = None
    email: str | None = None

    @property
    def key(self) -> TupleKey2:
        return (self.id, self.name)


class QiContext(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project: str | None = None
    entity: str | None = None
    task: str | None = None

    @property
    def key(self) -> TupleKey3:
        return (self.project, self.entity, self.task)


class QiSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    logical_id: str
    parent_logical_id: str | None = None
    tags: List[str] = Field(default_factory=list)

    @field_validator("logical_id")
    @classmethod
    def _validate_logical_id(cls, value: str) -> str:
        if not value or len(value) > 100:
            raise ValueError("logical_id must be 1-100 characters")
        return value


class QiMessage(BaseModel):
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
        # Fast validation - just check basic constraints
        if not value or len(value) > 200:
            raise ValueError("topic must be 1-200 characters")
        if "*" in value or ">" in value:
            raise ValueError("wildcards are disallowed")
        return value

    @field_validator("target")
    @classmethod
    def _validate_target(cls, value: list[str]) -> list[str]:
        if len(value) > 50:  # Prevent broadcast storms
            raise ValueError("target list cannot exceed 50 recipients")
        return value

    @field_validator("payload")
    @classmethod
    def _validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        # Basic check - just count top-level keys (fast)
        if len(value) > 100:  # Reasonable number of top-level keys
            raise ValueError("payload has too many top-level keys (max 100)")
        return value


@dataclass
class QiRequestTracker:
    reply_future: Future
    requesting_session_id: str


QiCallback: TypeAlias = Callable[..., Any]
QiHandler: TypeAlias = Callable[[QiMessage], Awaitable[Any] | Any]
