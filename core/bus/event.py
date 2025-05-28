"""
core/bus/event.py
-----------------

Message event models for Qi event bus.

• QiEvent: Main message wrapper with all routing info
• QiContext: Business context (project/entity/task)
• QiUser: User information for auth and routing
• QiSource: Source information for message routing
"""

import os
import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
#                               CONFIG / CONSTANTS                            #
# --------------------------------------------------------------------------- #

qi_dev_mode: bool = os.getenv("QI_DEV_MODE", "0") == "1"

# --------------------------------------------------------------------------- #
#                               EVENT MODELS                                  #
# --------------------------------------------------------------------------- #


class QiContext(BaseModel):
    """Business context for pipeline/project decisions."""

    project: Optional[str] = None
    entity: Optional[str] = None
    task: Optional[str] = None
    # TODO: Extra context can be added as needed

    @classmethod
    def from_env(cls) -> "QiContext":
        return cls(
            project=os.getenv("QI_PROJECT", None),
            entity=os.getenv("QI_ENTITY", None),
            task=os.getenv("QI_TASK", None),
        )


class QiUser(BaseModel):
    """User information for auth and user-specific routing."""

    id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    # TODO: auth tokens, permissions, etc.


class QiSource(BaseModel):
    """Source information for message routing."""

    session_id: Optional[str] = None
    window_id: Optional[str] = None
    addon: Optional[str] = None
    user: Optional[QiUser] = None


class QiEvent(BaseModel):
    """Canonical message wrapper with separated concerns."""

    model_config = ConfigDict(
        extra="forbid",
        validate_default=qi_dev_mode,
        validate_assignment=False,
        strict=qi_dev_mode,
    )

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = Field(default="")
    payload: Optional[dict[str, Any]] = Field(default_factory=dict)
    context: Optional[QiContext] = Field(default=None)
    source: Optional[QiSource] = Field(default=None)
    user: Optional[QiUser] = Field(default=None)
    reply_to: Optional[str] = Field(default=None)
    timestamp: float = Field(default_factory=time.time)


# --------------------------------------------------------------------------- #
#                               HELPER FUNCTIONS                              #
# --------------------------------------------------------------------------- #


def get_session_id_from_source(event: QiEvent) -> str:
    """Helper to extract session_id from event source."""
    return event.source.session_id if event.source else None


def get_addon_from_source(event: QiEvent) -> str:
    """Helper to extract addon from event source."""
    return event.source.addon if event.source else None


def get_window_id_from_source(event: QiEvent) -> Optional[str]:
    """Helper to extract window_id from event source."""
    return event.source.window_id if event.source else None
