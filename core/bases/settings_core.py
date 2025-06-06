# settings_core.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Type, get_args

from pydantic import BaseModel, Field, create_model

# ─── QiProp: holds a default + optional metadata ──────────────────────────────


class QiProp:
    """
    Wraps a default value + optional metadata (title/description/choices/etc.).
    Internally, this generates Pydantic Field(...) arguments when building the model.
    """

    __slots__ = ("default", "title", "description", "choices", "multi_select", "_extra")

    def __init__(
        self,
        default: int | str | float | bool | list[int | str | float] | None = None,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        choices: Optional[List[Any]] = None,
        multiselect: bool = False,
        **kwargs,
    ):
        self.default = default
        self.title = title
        self.description = description
        self.choices = choices
        self.multi_select = multiselect
        self._extra: dict[str, Any] = {}

    def specs(self, **kwargs: Any) -> None:
        """
        Post‐creation metadata editing. E.g.:
            p = QiProp(3, title="Age")
            p.specs(description="User’s age", choices=[18, 21, 30])
        """
        for k, v in kwargs.items():
            if k in ("default", "title", "description", "choices", "multiselect"):
                setattr(self, k, v)
            else:
                self._extra[k] = v

    def _field_info(self, annotation: Any) -> dict[str, Any]:
        """
        Convert this QiProp into a dict of kwargs for Pydantic’s Field():
        E.g., {"default": self.default, "title": ..., "description": ..., "enum": [...]}.
        """
        kwargs: dict[str, Any] = {"default": self.default}
        if self.title is not None:
            kwargs["title"] = self.title
        if self.description is not None:
            kwargs["description"] = self.description
        if self.choices is not None:
            kwargs["enum"] = self.choices
        if self.multi_select:
            # Pass x_multi_select so it appears in model_json_schema()
            kwargs["x_multi_select"] = True
        kwargs.update(self._extra)
        return kwargs


# ─── QiGroup: context‐manager builder for nested settings ─────────────────────


class QiGroup:
    """
    Each QiGroup can be used inside a class body as:

        settings = QiGroup()
        with settings as s:
            s.foo = 1
            s.bar = QiProp("hello", title="Greeting")
            s.subgroup = QiGroup(modifiable=True)
            with s.subgroup as sg:
                sg.x = 42

    At @define_settings time, we convert the tree into a Pydantic model.  At runtime,
    `self.settings` is a Pydantic instance with real attributes, giving dot‐notation
    and full linter support.
    """

    __slots__ = (
        "_children",
        "title",
        "description",
        "modifiable",
        "list_mode",
        "_defaults",
        "_parent",
        "_model_cls",
        "_model_instance",
    )

    def __init__(
        self,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        modifiable: bool = False,
        list: bool = False,
        **kwargs,
    ):
        object.__setattr__(self, "_children", {})
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "modifiable", modifiable)
        object.__setattr__(self, "list_mode", list)
        object.__setattr__(self, "_defaults", {})
        object.__setattr__(self, "_parent", None)
        # _model_cls and _model_instance get set by @define_settings later

    def __getattr__(self, name: str) -> Any:
        """
        Forward missing‐attribute lookups into self._children.
        Enables `with s.internal_profiles as p:` after `s.internal_profiles = QiGroup()`.
        """
        if name in self._children:
            return self._children[name]
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r}"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Capture `s.name = value` inside the `with`‐block:
        - QiGroup → register child group
        - QiProp → register leaf with metadata
        - Otherwise wrap in QiProp(default=value)
        Stored in self._children; no direct __dict__ assignment.
        """
        if name in (
            "_children",
            "title",
            "description",
            "modifiable",
            "list_mode",
            "_defaults",
            "_parent",
            "_model_cls",
            "_model_instance",
        ):
            object.__setattr__(self, name, value)
            return

        if isinstance(value, QiGroup):
            object.__setattr__(value, "_parent", self)
            self._children[name] = value
            return

        if isinstance(value, QiProp):
            self._children[name] = value
            return

        leaf = QiProp(value)
        self._children[name] = leaf

    def __deepcopy__(self, memo: dict[int, Any]) -> QiGroup:
        """
        Custom deepcopy: copy only the intended slots (_children, metadata, defaults)
        without triggering __getattr__. Recursively deep‐copy nested QiGroups/QiProps.
        """
        cls = type(self)
        new_group = cls(
            title=self.title,
            description=self.description,
            modifiable=self.modifiable,
            list=self.list_mode,
        )
        object.__setattr__(new_group, "_defaults", deepcopy(self._defaults, memo))

        new_children: Dict[str, Any] = {}
        for key, child in self._children.items():
            if isinstance(child, QiGroup):
                copied_child = child.__deepcopy__(memo)
                object.__setattr__(copied_child, "_parent", new_group)
                new_children[key] = copied_child
            else:
                new_children[key] = deepcopy(child, memo)
        object.__setattr__(new_group, "_children", new_children)
        object.__setattr__(new_group, "_parent", None)
        return new_group

    def __enter__(self) -> QiGroup:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    def set_defaults(self, values: dict[str, Any]) -> None:
        """
        Store override‐defaults that will be applied when building the Pydantic model.
        Example:
            settings.set_defaults({ "foo": 100, "nested": { "bar": "hello" } })
        """
        object.__setattr__(self, "_defaults", deepcopy(values))

    def inherit(self) -> QiGroup:
        """
        Return a deep copy of this entire group subtree, so you can override
        defaults independently from the original.
        """
        return deepcopy(self)

    def specs(self, **kwargs: Any) -> None:
        """
        Edit metadata on this group AFTER creation.
        Acceptable keys: title, description, modifiable, list
        """
        for k, v in kwargs.items():
            if k == "title":
                object.__setattr__(self, "title", v)
            elif k == "description":
                object.__setattr__(self, "description", v)
            elif k == "modifiable":
                object.__setattr__(self, "modifiable", v)
            elif k == "list":
                object.__setattr__(self, "list_mode", v)
            else:
                setattr(self, k, v)

    def _apply_defaults(self) -> None:
        """
        Recursively apply stored _defaults into QiProp.default or nested QiGroup._defaults.
        Clears _defaults afterward.
        """
        for name, override in self._defaults.items():
            if name not in self._children:
                continue
            child = self._children[name]
            if isinstance(child, QiProp):
                child.default = override
            elif isinstance(child, QiGroup) and isinstance(override, dict):
                object.__setattr__(child, "_defaults", deepcopy(override))
                child._apply_defaults()
        object.__setattr__(self, "_defaults", {})
        for child in self._children.values():
            if isinstance(child, QiGroup):
                child._apply_defaults()

    def _build_model(self, model_name: str = "RootModel") -> Type[BaseModel]:
        """
        Convert this QiGroup tree into a Pydantic BaseModel subclass.
        - Apply defaults via _apply_defaults()
        - For each QiProp, create (annotation, Field(**kwargs))
        - For each nested QiGroup, recurse
        Returns the new Pydantic model class.
        """
        self._apply_defaults()
        fields_def: Dict[str, Any] = {}

        for name, child in self._children.items():
            if isinstance(child, QiProp):
                py_default = child.default
                ann = type(py_default) if py_default is not None else Any
                if isinstance(py_default, list):
                    ann = (
                        List[get_args(py_default[0].__class__)]
                        if py_default
                        else List[Any]
                    )
                field_kwargs = child._field_info(ann)
                fields_def[name] = (ann, Field(**field_kwargs))
            else:
                nested_model = child._build_model(
                    model_name=name.capitalize() + "Model"
                )
                nested_default = nested_model(**{})
                fields_def[name] = (nested_model, Field(default=nested_default))

        ModelCls = create_model(
            model_name,
            __config__=type("C", (), {"validate_assignment": True}),
            **fields_def,  # type: ignore[arg-type]
        )
        return ModelCls

    def to_dict(self, instance: BaseModel) -> Dict[str, Any]:
        """
        Given a Pydantic model instance (created from this QiGroup), return a nested dict
        of all current values (defaults + overrides).
        """
        return instance.dict()

    def model_schema_json(self) -> Dict[str, Any]:
        """
        After @define_settings, returns the Pydantic model’s JSON‐schema as a dict.
        """
        if not hasattr(self, "_model_cls"):
            raise RuntimeError("You must call define_settings first.")
        return self._model_cls.model_json_schema()

    def _attach_model(self, model_cls: Type[BaseModel]) -> None:
        """
        Called by @define_settings: store the Pydantic model class and a default instance.
        """
        object.__setattr__(self, "_model_cls", model_cls)
        default_instance = model_cls(**{})  # fill in defaults
        object.__setattr__(self, "_model_instance", default_instance)


# ─── define_settings decorator ─────────────────────────────────────────────────


def define_settings(root_name: str):
    """
    Class decorator.  Use as:

        @define_settings(root_name="settings")
        class MyPlugin:
            settings = QiGroup()
            with settings as s:
                s.foo = 1
                s.bar = QiProp("hello", title="Greeting")
            settings.set_defaults({...})
            def process(self):
                print(self.settings.foo)
                print(self.settings.model_schema_json())

    What it does:
    1) Grabs `MyPlugin.settings` (a QiGroup), builds a Pydantic model from its _children.
    2) Attaches the model class to the QiGroup as _model_cls and a template instance as _model_instance.
    3) Replaces MyPlugin.__init__ so that on instantiation, `self.settings` becomes a deepcopy of the template instance.
    4) Adds helper methods `model_schema_json()` and `settings_dict()` to MyPlugin.
    """

    def decorator(plugin_cls: Type[Any]) -> Type[Any]:
        if not hasattr(plugin_cls, root_name):
            raise AttributeError(
                f"{plugin_cls.__name__} has no '{root_name}' attribute"
            )

        group: QiGroup = getattr(plugin_cls, root_name)
        if not isinstance(group, QiGroup):
            raise TypeError(f"'{root_name}' must be a QiGroup instance")

        # Build the Pydantic model from the QiGroup tree
        model_cls = group._build_model(model_name=root_name.capitalize() + "Model")
        group._attach_model(model_cls)

        orig_init = getattr(plugin_cls, "__init__", None)

        def __init__(self, *args, **kwargs):
            if orig_init is not None:
                orig_init(self, *args, **kwargs)
            default_model = deepcopy(group._model_instance)
            object.__setattr__(self, root_name, default_model)

        setattr(plugin_cls, "__init__", __init__)

        def model_schema_json(self) -> Dict[str, Any]:
            return group._model_cls.model_json_schema()

        setattr(plugin_cls, "model_schema_json", model_schema_json)

        def settings_dict(self) -> Dict[str, Any]:
            return getattr(self, root_name).dict()

        setattr(plugin_cls, "settings_dict", settings_dict)

        return plugin_cls

    return decorator
