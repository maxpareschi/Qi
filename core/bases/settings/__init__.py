# core/bases/settings/__init__.py

from typing import Any

from core.bases.settings.settings_builder import QiSettingsNode
from core.bases.settings.settings_decorator import define_settings
from core.bases.settings.settings_types import (
    Choices,
    Color,
    ColorAlpha,
    ColorFloat,
    ColorFloatAlpha,
    Meta,
    Vector2,
    Vector3,
    Vector4,
)

__all__ = (
    "Meta",
    "QiSettingsNode",
    "define_settings",
    "Any",
    "Choices",
    "Color",
    "ColorAlpha",
    "ColorFloat",
    "ColorFloatAlpha",
    "Vector2",
    "Vector3",
    "Vector4",
)
