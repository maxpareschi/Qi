# core/bases/plugins/plugin_base.py

import inspect
import os
import sys
from abc import ABC, abstractmethod
from collections import OrderedDict
from pathlib import Path
from typing import Any, Generic, Optional, Type, TypeVar
from uuid import uuid4

from pydantic import Field

from core.bases.models import (
    QiBaseModel,
    QiMessage,
    QiMessageType,
    QiSession,
)
from core.logger import get_logger

log = get_logger(__name__)

T = TypeVar("T")
KT = TypeVar("KT")
VT = TypeVar("VT")


#
# ─── 1) “FIELD DESCRIPTOR” CLASSES ───
#
class BaseSettingField:
    """
    Base for all setting-field descriptors. Used purely to capture metadata.
    """

    __slots__ = (
        "default",
        "label",
        "parent",
        "breakline",
        "visible_if",
        "enabled_if",
        "description",
    )

    def __init__(
        self,
        *,
        default: Any = None,
        label: Optional[str] = None,
        parent: Optional[str] = None,
        breakline: bool = True,
        visible_if: Optional[tuple[str, Any]] = None,
        enabled_if: Optional[tuple[str, Any]] = None,
        description: Optional[str] = None,
    ):
        """
        Args:
            default:     The default value for this setting.
            label:       UI label to show above/next to this field.
            parent:      If non-None, place this field under a named group.
            breakline:   If True, UI puts a visual break after this field.
            visible_if:  (other_field_name, expected_value) → only show if that field == value.
            enabled_if:  (other_field_name, expected_value) → only enable if that field == value.
            description: text to show as a tooltip/help-text.
        """
        self.default = default
        self.label = label
        self.parent = parent
        self.breakline = breakline
        self.visible_if = visible_if
        self.enabled_if = enabled_if
        self.description = description

    def __set_name__(self, owner: Any, name: str) -> None:
        # No actual storage on the Plugin class; PluginMeta will handle it.
        pass

    def __get__(self, instance: Any, owner: Any) -> Any:
        if instance is None:
            # Accessing via class: return the descriptor itself
            return self
        raise AttributeError(
            "Plugin authors should reference plugin.settings.<field_name>, not the descriptor."
        )

    def __set__(self, instance: Any, value: Any) -> None:
        raise AttributeError("Plugin authors do not set this attribute directly.")


class SettingField(BaseSettingField):
    """
    A simple scalar (str/int/bool/float) or enum-like field.

    Example:
        foo: str = SettingField(default="hello", label="Greeting")
    """


class MultiSelectField(BaseSettingField):
    """
    Acts like an enum with multiple-choice possible.

    `choices` must be a non-empty list of strings.
    """

    __slots__ = ("choices",)

    def __init__(
        self,
        *,
        choices: list[str],
        default: Optional[list[str]] = None,
        label: Optional[str] = None,
        parent: Optional[str] = None,
        breakline: bool = True,
        visible_if: Optional[tuple[str, Any]] = None,
        enabled_if: Optional[tuple[str, Any]] = None,
        description: Optional[str] = None,
    ):
        if not choices:
            raise ValueError(
                "MultiSelectField: `choices` must be a non-empty list of strings."
            )
        super().__init__(
            default=default or [],
            label=label,
            parent=parent,
            breakline=breakline,
            visible_if=visible_if,
            enabled_if=enabled_if,
            description=description,
        )
        self.choices = choices


class ListField(BaseSettingField, Generic[T]):
    """
    A list of items of type T.

    Example:
        lucky_numbers: list[int] = ListField(int, default=[7, 13], label="Lucky Numbers")
    """

    __slots__ = ("item_type",)

    def __init__(
        self,
        item_type: Type[T],
        *,
        default: Optional[list[T]] = None,
        label: Optional[str] = None,
        parent: Optional[str] = None,
        breakline: bool = True,
        visible_if: Optional[tuple[str, Any]] = None,
        enabled_if: Optional[tuple[str, Any]] = None,
        description: Optional[str] = None,
    ):
        super().__init__(
            default=default or [],
            label=label,
            parent=parent,
            breakline=breakline,
            visible_if=visible_if,
            enabled_if=enabled_if,
            description=description,
        )
        self.item_type = item_type


class DictField(BaseSettingField, Generic[KT, VT]):
    """
    A dict mapping keys of type KT to values of type VT.

    Example:
        options: dict[str, str] = DictField(str, str, default={"a": "1", "b": "2"})
    """

    __slots__ = ("key_type", "value_type")

    def __init__(
        self,
        key_type: Type[KT],
        value_type: Type[VT],
        *,
        default: Optional[dict[KT, VT]] = None,
        label: Optional[str] = None,
        parent: Optional[str] = None,
        breakline: bool = True,
        visible_if: Optional[tuple[str, Any]] = None,
        enabled_if: Optional[tuple[str, Any]] = None,
        description: Optional[str] = None,
    ):
        super().__init__(
            default=default or {},
            label=label,
            parent=parent,
            breakline=breakline,
            visible_if=visible_if,
            enabled_if=enabled_if,
            description=description,
        )
        self.key_type = key_type
        self.value_type = value_type


class OrderedDictField(BaseSettingField, Generic[KT, VT]):
    """
    An OrderedDict mapping. Stored as a plain dict underneath, but UI can show “order.”

    Example:
        sequence: OrderedDictField(str, int, default=OrderedDict([("a", 1), ("b", 2)]))
    """

    __slots__ = ("key_type", "value_type")

    def __init__(
        self,
        key_type: Type[KT],
        value_type: Type[VT],
        *,
        default: Optional[OrderedDict[KT, VT]] = None,
        label: Optional[str] = None,
        parent: Optional[str] = None,
        breakline: bool = True,
        visible_if: Optional[tuple[str, Any]] = None,
        enabled_if: Optional[tuple[str, Any]] = None,
        description: Optional[str] = None,
    ):
        super().__init__(
            default=default or OrderedDict(),
            label=label,
            parent=parent,
            breakline=breakline,
            visible_if=visible_if,
            enabled_if=enabled_if,
            description=description,
        )
        self.key_type = key_type
        self.value_type = value_type


class GroupField(BaseSettingField):
    """
    A purely visual “group” in the UI; does not correspond to a real setting value.
    """

    __slots__ = ("name",)

    def __init__(
        self,
        *,
        name: str,
        label: Optional[str] = None,
        parent: Optional[str] = None,
        breakline: bool = True,
        description: Optional[str] = None,
    ):
        super().__init__(
            default=None,
            label=label or name,
            parent=parent,
            breakline=breakline,
            visible_if=None,
            enabled_if=None,
            description=description,
        )
        self.name = name


#
# ─── 2) PluginMeta ───
#
class PluginMeta(type):
    """
    Metaclass for PluginBase. When a Plugin subclass is defined, we scan its
    class dict for any BaseSettingField instances. We then build a Pydantic
    model (subclass of QiBaseModel) named `<PluginClassName>Settings` with those fields.
    Finally, we strip those descriptors off the class and set `settings_model_cls`.
    """

    def __new__(cls, name, bases, namespace, **kwargs):
        # 1) Collect all BaseSettingField descriptors from namespace
        field_items: dict[str, BaseSettingField] = {
            attr_name: attr_val
            for attr_name, attr_val in namespace.items()
            if isinstance(attr_val, BaseSettingField)
        }

        # 2) Build a Pydantic model dynamically
        pydantic_fields: dict[str, tuple[type[Any], Field]] = {}
        for field_name, descriptor in field_items.items():
            # Infer Python type from annotation if given
            annotation = namespace.get("__annotations__", {}).get(field_name, Any)

            extra_metadata: dict[str, Any] = {
                "label": descriptor.label or field_name,
                "parent": descriptor.parent,
                "breakline": descriptor.breakline,
                "visible_if": descriptor.visible_if,
                "enabled_if": descriptor.enabled_if,
                "description": descriptor.description,
            }

            if isinstance(descriptor, MultiSelectField):
                python_type = list[str]
                extra_metadata["choices"] = descriptor.choices
                default_val = descriptor.default
            elif isinstance(descriptor, ListField):
                python_type = list[descriptor.item_type]  # e.g. list[int]
                default_val = descriptor.default
            elif isinstance(descriptor, DictField):
                python_type = dict[descriptor.key_type, descriptor.value_type]
                default_val = descriptor.default
            elif isinstance(descriptor, OrderedDictField):
                python_type = dict[descriptor.key_type, descriptor.value_type]
                extra_metadata["ordered"] = True
                default_val = descriptor.default
            elif isinstance(descriptor, GroupField):
                # GroupField is purely visual; skip adding a real field
                python_type = Any
                default_val = None
                extra_metadata["is_group"] = True
            else:
                # Simple SettingField
                python_type = (
                    annotation
                    if annotation is not Any
                    else type(descriptor.default or "")
                )
                default_val = descriptor.default

            pydantic_fields[field_name] = (
                python_type,
                Field(default_val, **extra_metadata),
            )

        # Dynamically create a Pydantic subclass
        settings_model_name = f"{name}Settings"
        SettingsModel = type(
            settings_model_name,
            (QiBaseModel,),
            {
                "__annotations__": {k: v[0] for k, v in pydantic_fields.items()},
                **{k: v[1] for k, v in pydantic_fields.items()},
            },
        )

        # 3) Remove descriptor attributes from the class namespace
        for field_name in field_items:
            namespace.pop(field_name, None)

        # 4) Attach settings_model_cls to the plugin class
        namespace["settings_model_cls"] = SettingsModel

        return super().__new__(cls, name, bases, namespace, **kwargs)


#
# ─── 3) PluginBase class ───
#
class PluginBase(ABC, metaclass=PluginMeta):
    """
    Base class for all Qi plugins. Subclasses must implement:

      - `async def discover(self) -> None:`
      - `async def process(self, message: QiMessage) -> Any:`

    Provides:
      - Automatic settings model (`self.settings`) built from class-level descriptors.
      - `register(...)` and `unregister()` hooks to connect into a central MessageBus.
      - A `_process_wrapper(...)` that dispatches and returns replies when needed.
    """

    def __init__(self, *, settings_overrides: dict[str, Any] | None = None):
        # Unique plugin ID
        self.plugin_id: str = str(uuid4())

        # Instantiate the settings model using any overrides
        overrides = settings_overrides or {}
        self.settings = self.settings_model_cls(**overrides)

        # Track registration state
        self._is_registered: bool = False

    @abstractmethod
    async def discover(self) -> None:
        """
        Called once, when this plugin is first registered.
        Perform initialization here (e.g., load resources).
        """
        ...

    @abstractmethod
    async def process(self, message: QiMessage) -> Any:
        """
        Called whenever a QiMessage relevant to this plugin arrives.
        Return a value if this plugin should reply (REQUEST); return None if just handling EVENT.
        """
        ...

    async def register(self, *, hub_session: QiSession) -> None:
        """
        Register this plugin with the central message bus/hub.

        Typical steps:
          1) Remember our own QiSession (hub_session).
          2) Call self.discover().
          3) Subscribe to topic (if `_topic_` is defined).
        """
        if self._is_registered:
            log.warning(f"Plugin {self.plugin_id} already registered; skipping.")
            return

        self.hub_session = hub_session
        await self.discover()

        topic = getattr(self, "_topic_", None)
        if topic:
            from core.messaging.message_bus import QiMessageBus

            QiMessageBus.instance().subscribe(
                topic=topic,
                handler=self._process_wrapper,
                session_id=hub_session.logical_id,
            )

        self._is_registered = True
        log.info(
            f"Plugin {self.plugin_id} registered under session {hub_session.logical_id}."
        )

    async def unregister(self) -> None:
        """
        Unregister this plugin: unsubscribe its handler and clean up.
        """
        if not self._is_registered:
            return

        topic = getattr(self, "_topic_", None)
        if topic:
            from core.messaging.message_bus import QiMessageBus

            QiMessageBus.instance().unsubscribe(
                topic=topic,
                handler=self._process_wrapper,
                session_id=self.hub_session.logical_id,
            )

        self._is_registered = False
        log.info(f"Plugin {self.plugin_id} unregistered.")

    async def _process_wrapper(self, qi_message: QiMessage) -> Any:
        """
        Wraps self.process(...) so that:
          - If `qi_message.type == QiMessageType.REQUEST`, we await `process()` and return its result.
          - Otherwise (EVENT or REPLY), we call process() and ignore its return.
        """
        try:
            if qi_message.type == QiMessageType.REQUEST:
                result = await self.process(qi_message)
                return result
            else:
                await self.process(qi_message)
        except Exception as e:
            log.exception(f"Plugin {self.plugin_id} error in process(): {e}")
            if qi_message.type == QiMessageType.REQUEST:
                return {"error": str(e)}


#
# ─── 4) Example Concrete Plugin ───
#
class ExamplePlugin(PluginBase):
    """
    Example plugin that:
      - Subscribes to topic “example.do_something”
      - Exposes several settings for demonstration.
    """

    _topic_: str = "example.do_something"

    # Simple fields
    foo: str = SettingField(default="hello", label="Greeting")
    bar: int = SettingField(default=10, label="Count", visible_if=("foo", "hello"))

    # Multi-select
    colors: list[str] = MultiSelectField(
        choices=["red", "green", "blue"],
        default=["red"],
        label="Favorite Colors",
        breakline=False,
    )

    # List of ints
    lucky_numbers: list[int] = ListField(int, default=[7, 13], label="Lucky Numbers")

    # Group for “advanced” fields
    advanced: None = GroupField(name="advanced", label="Advanced Settings")

    # Two fields under “advanced”
    threshold: float = SettingField(default=0.5, label="Threshold", parent="advanced")
    options: dict[str, str] = DictField(
        str, str, default={"a": "1", "b": "2"}, parent="advanced"
    )

    async def discover(self) -> None:
        log.info(
            f"ExamplePlugin({self.plugin_id}) discovered with settings: {self.settings.dict()}"
        )

    async def process(self, message: QiMessage) -> Any:
        log.info(
            f"ExamplePlugin got message: topic={message.topic}, payload={message.payload}"
        )
        if message.type == QiMessageType.REQUEST:
            return {"echo": message.payload, "greeting": self.settings.foo}
        return None


#
# ─── 5) Plugin Discovery Helper ───
#
def discover_plugins_from_folder(folder_path: str) -> list[Type[PluginBase]]:
    """
    Walk `folder_path` recursively. For each .py file:
      - Import it under a unique module name
      - Collect any subclass of PluginBase (excluding PluginBase itself)
    Return the list of plugin classes found.
    """
    import importlib.util

    found: list[Type[PluginBase]] = []
    folder_path = Path(folder_path).resolve()

    for root, _, files in os.walk(folder_path):
        for fname in files:
            if not fname.endswith(".py"):
                continue

            full_path = Path(root) / fname
            module_name = f"addon_{full_path.stem}_{uuid4().hex}"
            spec = importlib.util.spec_from_file_location(module_name, str(full_path))
            if not spec or not spec.loader:
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, PluginBase)
                    and attr is not PluginBase
                ):
                    found.append(attr)

    return found
