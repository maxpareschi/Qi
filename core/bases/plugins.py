# core/bases/plugins.py

import abc
from typing import Any, Type

from core.bases.settings import QiSetting, QiSettingsNode


class QiPluginBaseMeta(abc.ABCMeta):
    """
    Metaclass for all Qi plugins.  Automates:
      1) Instantiating a 'settings' attribute (a QiSettingsNode) if none provided.
      2) Collecting any class-level attributes (that are not reserved, not callables)
         and moving them into 'settings' as QiSetting leaves.
      3) Honoring any explicit QiSetting instances (so plugin authors can write
         'foo = QiSetting(42, label="Foo")' at class-level).
      4) Enforcing that 'name' is a reserved keyword (can be overridden to rename plugin).
    """

    # You can expand this set if there are other class-level names you want reserved.
    _reserved_keys: set[str] = {"settings", "name"}

    def __new__(
        cls, class_name: str, bases: tuple[Type, ...], namespace: dict[str, Any]
    ):
        # 1) Ensure there is a 'settings' in the namespace (or supply a fresh one)
        settings_node: QiSettingsNode = namespace.get("settings", QiSettingsNode())
        namespace["settings"] = settings_node

        # 2) If a 'name' was provided at class-level, keep it; otherwise default to the class name.
        plugin_name = namespace.get("name", class_name)
        if not isinstance(plugin_name, str):
            raise TypeError(
                f"Plugin name must be a str, got {type(plugin_name).__name__}"
            )
        namespace["name"] = plugin_name

        # 3) Create the class object
        new_cls: QiPluginBase = super().__new__(cls, class_name, bases, namespace)

        # 4) Move any “non-reserved, non-callable, non-dunder” attributes into settings
        for key, value in list(namespace.items()):
            if key in QiPluginBaseMeta._reserved_keys or key.startswith("__"):
                continue

            # If the value is already a QiSetting, attach it under 'settings'
            if isinstance(value, QiSetting):
                value._parent_node = settings_node
                value._key_in_parent = key
                settings_node._children_schema[key] = value
                delattr(new_cls, key)

            # If the value is a QiSettingsNode, keep it as is under settings
            elif isinstance(value, QiSettingsNode):
                value._parent = settings_node
                value._key_in_parent = key
                value._defaults_root = settings_node._defaults_root
                settings_node._children_schema[key] = value
                delattr(new_cls, key)

            # Otherwise, if not callable, wrap it in QiSetting(default=value):
            elif not callable(value):
                wrapped = QiSetting(default=value)
                wrapped._parent_node = settings_node
                wrapped._key_in_parent = key
                settings_node._children_schema[key] = wrapped
                delattr(new_cls, key)

            # If 'value' was callable (methods, etc.), leave it alone.

        # Finally, store the plugin’s 'name' on the class for easy reference
        new_cls.name = plugin_name
        return new_cls


class QiPluginBase(metaclass=QiPluginBaseMeta):
    """
    Abstract base class for all Qi plugins.  Provides:
      • A pre-created 'settings: QiSettingsNode' on the class.
      • Reserved keyword 'name' (plugin display name or unique ID).
      • Three abstract methods that every plugin must implement:
          - discover():   run at startup to discover resources or sub-plugins
          - register():   register handlers or connections into the bus/hub
          - process():    the main “work” method (may be async or sync)
      • A helper 'self.settings' to access the nested settings tree.
      • A helper 'self.get_defaults()' to get a plain dict of current defaults.
      • A helper 'self.get_schema()' to get the schema dict for UI.
    """

    # Plugin authors may override these reserved class-level attributes:
    # • 'name': if you want a human-friendly or ID string (default = class name).
    name: str

    settings: QiSettingsNode  # pre-populated by the metaclass

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Subclasses may load defaults here by calling super().__init__()
        pass

    @abc.abstractmethod
    def discover(self) -> None:
        """
        Discover any resources, sub-plugins, file paths, etc., needed at startup.
        Called once (synchronously) by the hub before 'register()'.
        """

    @abc.abstractmethod
    def register(self) -> None:
        """
        Register this plugin’s handlers, commands, or connections into the message bus/hub.
        Called once (synchronously) after 'discover()'.
        """

    @abc.abstractmethod
    async def process(self) -> None:
        """
        The main processing logic of this plugin.
        Implementers may perform async calls (e.g., I/O, network).
        This method may be invoked by the hub in response to messages or on a schedule.
        """

    def get_schema(self) -> dict[str, Any]:
        """
        Return the schema of all settings under this plugin as a nested dict.
        This is typically rendered to JSON for a UI form generator.
        """
        return self.settings.get_schema()

    def get_defaults(self) -> Any:
        """
        Return the current default-values under this plugin’s settings as a pure Python
        structure (dict or list).  Useful for sending to a UI or for persisting.
        """
        return self.settings.get_values()

    def __repr__(self) -> str:
        return f"<QiPlugin(name={self.name!r})>"
