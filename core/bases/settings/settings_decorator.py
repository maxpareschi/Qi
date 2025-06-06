# core/bases/settings/settings_decorator.py

from __future__ import annotations

from typing import Any, Type

from core.bases.settings.settings_builder import QiSettingsNode


def define_settings(*, root_name: str = "settings"):
    """
    Class decorator that injects a new QiSettingsNode under 'root_name' and
    scans class-level annotations/defaults to populate it.

    Usage:
        @define_settings(root_name="config")
        class MyPlugin:
            config = <injected QiSettingsNode>
            config.foo: int = 5
            with config.subgroup as sg:
                sg.bar: str = "hello"
    """

    def _decorator(cls: Type) -> Type:
        # 1) Create a fresh QiSettingsNode and assign it to cls.<root_name>
        root_node = QiSettingsNode(parent=None, name=root_name, metadata={})
        setattr(cls, root_name, root_node)

        # 2) Collect reserved names to skip (anything starting with "_",
        #    plus any in __settings_reserved__)
        reserved = set()
        for name in dir(cls):
            if name.startswith("_"):
                reserved.add(name)
        reserved.update(getattr(cls, "__settings_reserved__", []))

        # 3) Inspect class annotations to bind any defaults already provided.
        #    We walk through cls.__dict__; any (name, value) where name not in reserved,
        #    and name is in __annotations__, becomes a field under root_node.
        annotations = getattr(cls, "__annotations__", {})
        for name, annotation in annotations.items():
            if name in reserved:
                continue
            # If the class already set a default (cls.__dict__[name]), capture it:
            if name in cls.__dict__:
                default = getattr(cls, name)
            else:
                default = None

            # Now assign that to root_node; this invokes QiSettingsNode.__setattr__
            # which creates a SettingsLeaf under root_node._children[name]
            setattr(root_node, name, default)

        # 4) Finally, remove any of those class-level attributes so they don't shadow:
        #    (We only want them inside the builder, not as real class vars)
        for name in annotations:
            if name not in reserved and hasattr(cls, name):
                delattr(cls, name)

        # 5) Wrap __init__ so that each instance gets a fresh copy of the settings tree
        orig_init = getattr(cls, "__init__", None)

        def __init__(self, *args: Any, **kwargs: Any):
            # Deep-clone the root_node so every instance has its own
            self_root = root_node.inherit()  # clone the entire schema & defaults
            setattr(self, root_name, self_root)

            # Call original __init__ (plugin’s own)
            if orig_init is not None:
                orig_init(self, *args, **kwargs)

        setattr(cls, "__init__", __init__)

        return cls

    return _decorator
