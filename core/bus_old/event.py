"""
core/bus/event.py
-----------------

Message event models for Qi event bus.

• QiEvent: Main message wrapper with all routing info
• QiContext: Business context (project/entity/task)
• QiUser: User information for auth and routing
• QiSource: Source information for message routing
"""

import os  # core/bus/event.py
import time
import uuid
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# Respect your dev-mode flags
qi_dev_mode: bool = os.getenv("QI_DEV_MODE", "0") == "1"


class QiContext(BaseModel):
    project: Optional[str] = None
    entity: Optional[str] = None
    task: Optional[str] = None

    @classmethod
    def from_env(cls) -> "QiContext":
        return cls(
            project=os.getenv("QI_PROJECT", None),
            entity=os.getenv("QI_ENTITY", None),
            task=os.getenv("QI_TASK", None),
        )


class QiUser(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    # TODO: add more fields for pwd, auth tokens, etc.


class QiSource(BaseModel):
    addon: str = None
    session_id: str = None
    window_id: Optional[str] = None
    user: Optional[QiUser] = None


class QiEvent(BaseModel):
    """
    Canonical message wrapper with routing info.
    - Accepts `data=…` as an alias for `payload`.
    - Allows `timestamp` to be float or string (for your tests).
    """

    model_config = ConfigDict(
        extra="forbid",
        strict=qi_dev_mode,
        validate_assignment=False,
        populate_by_name=True,  # allow using field aliases in constructor
    )

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = Field(default="")
    # alias `data` → populates `payload`
    payload: Optional[dict[str, Any]] = Field(default_factory=dict, alias="data")

    context: Optional[QiContext] = None
    source: Optional[QiSource] = None
    user: Optional[QiUser] = None
    reply_to: Optional[str] = None
    timestamp: Union[float, str] = Field(default_factory=time.time)
