# core/bundle/models.py

from __future__ import annotations

from pydantic import BaseModel, Field

from core.models import QiBaseModel


class Bundle(QiBaseModel):
    """
    Defines a bundle, which is a collection of addons and environment variables
    that can be activated for a session.
    """

    name: str = Field(..., description="The name of the bundle.")
    allow_list: list[str] = Field(
        default_factory=list, description="A list of addon names to allow."
    )
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the bundle."
    )


class Bundles(BaseModel):
    """A container for a dictionary of bundles, matching the TOML structure."""

    bundles: dict[str, Bundle] = Field(
        default_factory=dict, description="A mapping of bundle names to bundle objects."
    )
