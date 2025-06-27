# core/settings.py

"""
This module contains the base class for the Qi settings.
"""

from copy import deepcopy
from threading import RLock
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    create_model,
)

_STANDARD_FIELD_ARGS = {
    "title",
    "description",
    "alias",
    "validation_alias",
    "serialization_alias",
    "field_validator",
    "serializer",
    "frozen",
    "validate_default",
    "repr",
    "init",
    "init_var",
    "kw_only",
    "pattern",
    "strict",
    "gt",
    "ge",
    "lt",
    "le",
    "multiple_of",
    "allow_inf_nan",
    "max_digits",
    "decimal_places",
    "min_length",
    "max_length",
    "union_mode",
}


# ────────────────────────────────────────────────────────────
#  QiProp – leaf node
# ────────────────────────────────────────────────────────────
class QiProp:
    """
    Leaf setting.

    Parameters
    ----------
    default
        Scalar or collection default value.
    title, description
        Optional UI annotations.
    **kwargs
        Arbitrary metadata forwarded verbatim into Field(...).
    """

    def __init__(
        self,
        default: int
        | str
        | float
        | bool
        | list[Any]
        | tuple[Any]
        | set[Any]
        | None = None,
        *,
        title: str | None = None,
        description: str | None = None,
        **kwargs: Any,
    ):
        self.default = default
        self.title = title
        self.description = description
        self._meta: dict[str, Any] = kwargs.copy()

    # ------------ public helpers ------------ #
    def set_options(self, **kwargs: Any) -> None:
        """
        Update built-in attributes or extend metadata in place.
        """
        for k, v in kwargs.items():
            if k in {"default", "title", "description"}:
                setattr(self, k, v)
            else:
                self._meta[k] = v

    # ------------- internal -------------- #
    def _field_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {"default": self.default}
        if self.title is not None:
            info["title"] = self.title
        if self.description is not None:
            info["description"] = self.description

        # Add any extra metadata to json_schema_extra
        extra_meta = {
            k: v for k, v in self._meta.items() if k not in _STANDARD_FIELD_ARGS
        }
        if extra_meta:
            info["json_schema_extra"] = extra_meta

        # Add standard field arguments directly
        for k, v in self._meta.items():
            if k in _STANDARD_FIELD_ARGS:
                info[k] = v

        return info

    def _signature(self) -> str:
        return f"PROP|{type(self.default).__name__}|{repr(sorted(self._meta.items()))}"


# ────────────────────────────────────────────────────────────
#  QiGroup – interior node
# ────────────────────────────────────────────────────────────
class QiGroup:
    """
    QiGroup node with three modes:

    1. Direct object (modifiable=False): SubModel - single nested object
    2. Collection (modifiable=True, list_mode=False): dict[str, SubModel] - mapping
    3. List (modifiable=True, list_mode=True): list[SubModel] - list
    """

    # ------------ construction ------------ #
    def __init__(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        list_mode: bool = False,
        default_key: str | None = None,
        modifiable: bool = False,
        **kwargs: Any,
    ):
        if list_mode and default_key:
            raise ValueError("list_mode=True conflicts with default_key")
        if default_key and not modifiable:
            raise ValueError("default_key requires modifiable=True")

        self.list_mode: bool = bool(list_mode)
        self.modifiable: bool = bool(modifiable)
        self._default_key_hint: str | None = default_key

        self.title = title
        self.description = description
        self._meta: dict[str, Any] = kwargs.copy()

        # definition-time data
        self._children: dict[str, QiProp | "QiGroup"] = {}
        self._defaults: dict[str, Any] = {}
        self._parent: QiGroup | None = None
        self._parent_key: str | None = None

        # run-time data
        self._model_cls: type[BaseModel] | None = None
        self._model_instance: BaseModel | None = None
        self._lock = RLock()

    # ------------ deepcopy (inherit) ------------ #
    def __deepcopy__(self, memo: dict[int, Any]) -> "QiGroup":
        clone = type(self)(
            title=self.title,
            description=self.description,
            list_mode=self.list_mode,
            default_key=self._default_key_hint,
            modifiable=self.modifiable,
            **deepcopy(self._meta, memo),
        )
        clone._defaults = deepcopy(self._defaults, memo)
        clone._lock = RLock()
        for name, child in self._children.items():
            clone_dest = deepcopy(child, memo)
            if isinstance(clone_dest, QiGroup):
                clone_dest._parent = clone
                clone_dest._parent_key = name
            clone._children[name] = clone_dest
        memo[id(self)] = clone
        return clone

    # --------------- context manager --------------- #
    def __enter__(self) -> "QiGroup":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # For modifiable collections, capture current state as default entry
        if self.modifiable and not self.list_mode and not self._defaults:
            key = self._default_key_hint or "_auto"
            # Capture the current state of this group as the default entry
            default_entry = {}
            for child_name, child in self._children.items():
                if isinstance(child, QiProp):
                    default_entry[child_name] = child.default
                elif isinstance(child, QiGroup):
                    # For nested groups, get their current defaults recursively
                    default_entry[child_name] = child._get_current_defaults()
            self._defaults[key] = default_entry

    # --------------- attribute plumbing --------------- #
    def __getattr__(self, name: str) -> Any:
        # Always check for original children first, even after build
        # This allows access to QiGroup objects for methods like inherit()
        if name in self._children:
            return self._children[name]

        # For runtime data access, use the model instance
        if self._model_instance is not None:
            with self._lock:
                try:
                    return getattr(self._model_instance, name)
                except AttributeError:
                    pass

        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        internals = {
            "title",
            "description",
            "_meta",
            "_children",
            "_defaults",
            "_parent",
            "_parent_key",
            "_model_cls",
            "_model_instance",
            "_lock",
            "list_mode",
            "modifiable",
            "_default_key_hint",
        }
        if name in internals or name.startswith("_"):
            object.__setattr__(self, name, value)
            return

        if self._model_instance is not None:
            with self._lock:
                setattr(self._model_instance, name, value)
            return

        # definition-time assignment
        if isinstance(value, QiGroup):
            value._parent = self
            value._parent_key = name
            self._children[name] = value
        elif isinstance(value, QiProp):
            self._children[name] = value
        else:
            self._children[name] = QiProp(value)

    # ---------------- public helpers ---------------- #
    def set_options(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if k in {"title", "description"}:
                    setattr(self, k, v)
                else:
                    self._meta[k] = v

    def set_default_key(self, key: str) -> None:
        """
        Override the key used for the auto-snapshot.  Call **before** the first
        build() (i.e. still in definition mode).
        """
        if self._model_instance is not None:
            raise RuntimeError("set_default_key() must be called before build()")
        if self.list_mode:
            raise RuntimeError("default_key applies only to mapping groups")
        if not self.modifiable:
            raise RuntimeError("default_key applies only to modifiable groups")
        self._default_key_hint = key

    def set_defaults(self, values: dict[str, Any]) -> None:
        """
        Merge *values* into the defaults under this subtree and rebuild the
        root model so changes are visible immediately.
        """
        with self._lock:
            # Simple approach: merge new defaults with existing ones
            for key, value in values.items():
                child = self._children.get(key)
                if isinstance(child, QiGroup):
                    # For child groups, merge into their defaults
                    if isinstance(value, dict):
                        child._defaults.update(value)
                    else:
                        child._defaults[key] = value
                else:
                    # For non-group children, set in our defaults
                    self._defaults[key] = value
            self._find_root().build()

    def inherit(self, *, defaults: bool = True) -> "QiGroup":
        """
        Deep-copy this subtree.

        Parameters
        ----------
        defaults
            True  → copy the stored declarative defaults (default behaviour).
            False → schema-only clone.
        """
        clone = deepcopy(self)
        if not defaults:
            # Clear all defaults recursively
            clone._clear_defaults_recursive()
        return clone

    def _clear_defaults_recursive(self) -> None:
        """Clear defaults recursively from this group and all children."""
        self._defaults = {}
        for child in self._children.values():
            if isinstance(child, QiGroup):
                child._clear_defaults_recursive()

    # ------------- defaults machinery ------------- #
    def _apply_defaults(self) -> None:
        """Apply defaults to children (simplified version)."""
        with self._lock:
            for key, override in deepcopy(self._defaults).items():
                child = self._children.get(key)
                if isinstance(child, QiProp):
                    child.default = override
                elif isinstance(child, QiGroup):
                    child._defaults.update(
                        override if isinstance(override, dict) else {key: override}
                    )
                    child._apply_defaults()
            # Don't clear _defaults here - keep them for collections

    # ---------------- helpers ---------------- #
    def _find_root(self) -> "QiGroup":
        node: QiGroup = self
        while node._parent is not None:
            node = node._parent
        return node

    def _get_current_defaults(self) -> dict[str, Any]:
        """
        Get the current default values for this group's children.
        Used for capturing state in collection groups.
        """
        if self.modifiable and not self.list_mode:
            # For collections, return the collection entries
            return deepcopy(self._defaults)
        else:
            # For regular groups, capture current field values (not recursive defaults)
            defaults = {}
            for child_name, child in self._children.items():
                if isinstance(child, QiProp):
                    defaults[child_name] = child.default
                elif isinstance(child, QiGroup) and not child.modifiable:
                    # For non-modifiable nested groups, capture their field structure
                    defaults[child_name] = child._get_current_defaults()
                # Skip modifiable groups to avoid circular references
            return defaults

    def _signature(self) -> str:
        parts = []
        for child_name, child in sorted(self._children.items()):
            if isinstance(child, QiGroup):
                parts.append(
                    (
                        "G",
                        child_name,
                        child._signature(),
                        repr(sorted(child._meta.items())),
                        child.list_mode,
                        child.modifiable,
                        child._default_key_hint,
                    )
                )
            else:
                parts.append(("P", child_name, child._signature()))
        return (
            repr(parts)
            + "|"
            + repr(sorted(self._meta.items()))
            + "|"
            + str(self.list_mode)
            + "|"
            + str(self.modifiable)
            + "|"
            + repr(self._default_key_hint)
        )

    # ------------- model building ------------- #
    def _build_model(
        self, name: str, cache: dict[str, type[BaseModel]]
    ) -> type[BaseModel]:
        with self._lock:
            sig = self._signature()
            if sig in cache:
                return cache[sig]

            self._apply_defaults()
            fields: dict[str, tuple[Any, Any]] = {}

            for field_name, child in self._children.items():
                if isinstance(child, QiProp):
                    default = child.default
                    if isinstance(default, (list, tuple, set)):
                        kinds = {type(x) for x in default}
                        if len(kinds) > 1:
                            raise TypeError("heterogeneous list/tuple/set defaults")
                        inner = kinds.pop() if default else Any
                        ann: Any = list[inner]
                    else:
                        ann = type(default) if default is not None else Any
                    fields[field_name] = (ann, Field(**child._field_info()))
                elif isinstance(child, QiGroup):
                    sub_cls = child._build_model(
                        field_name.capitalize() + "Model", cache
                    )

                    # Prepare field info with proper separation of standard args and extras
                    field_info = {}
                    if child.title is not None:
                        field_info["title"] = child.title
                    if child.description is not None:
                        field_info["description"] = child.description

                    # Separate standard field arguments from JSON schema extras

                    extra_meta = {
                        k: v
                        for k, v in child._meta.items()
                        if k not in _STANDARD_FIELD_ARGS
                    }
                    if extra_meta:
                        field_info["json_schema_extra"] = extra_meta

                    # Add standard field arguments directly
                    for k, v in child._meta.items():
                        if k in _STANDARD_FIELD_ARGS:
                            field_info[k] = v

                    # Three modes:
                    if child.modifiable and child.list_mode:
                        # Mode 1: List of models
                        ann = list[sub_cls]

                        # Add support for default items
                        def list_factory():
                            return [
                                sub_cls(**item) for item in child._defaults.values()
                            ]

                        field = Field(default_factory=list_factory, **field_info)
                    elif child.modifiable and not child.list_mode:
                        # Mode 2: Dictionary of models (collection)
                        ann = dict[str, sub_cls]

                        # Create factory that populates with defaults
                        def make_collection_factory(defaults_dict, sub_model_cls):
                            def factory():
                                result = {}
                                for key, default_values in defaults_dict.items():
                                    if isinstance(default_values, dict):
                                        result[key] = sub_model_cls(**default_values)
                                    # Skip non-dict values to avoid errors
                                return result

                            return factory

                        factory_func = make_collection_factory(child._defaults, sub_cls)
                        field = Field(default_factory=factory_func, **field_info)
                    else:
                        # Mode 3: Direct nested model (not modifiable)
                        ann = sub_cls
                        field = Field(default_factory=sub_cls, **field_info)

                    fields[field_name] = (ann, field)

            cls = create_model(
                name,
                __config__=ConfigDict(validate_assignment=True),
                **fields,  # type: ignore[arg-type]
            )
            cache[sig] = cls
            return cls

    def build(self) -> None:
        """
        Build (or rebuild) the Pydantic model tree starting from the root.
        """
        with self._lock:
            if not isinstance(self, QiSettings):
                raise RuntimeError("build() is allowed only on root QiSettings")
            cache: dict[str, type[BaseModel]] = {}
            self._model_cls = self._build_model(self.title or "RootModel", cache)
            self._model_instance = self._model_cls(**{})

    # -------------- read helpers ------------- #
    def _assert_built(self) -> None:
        if self._model_instance is None:
            raise RuntimeError(
                "QiSettings not built yet. "
                "Use the 'with QiSettings() as s:' pattern or call .build() after definitions."
            )

    def get_values(self) -> dict[str, Any]:
        self._assert_built()
        with self._lock:
            return self._model_instance.model_dump()

    def get_model_schema(self) -> dict[str, Any]:
        self._assert_built()
        with self._lock:
            return self._model_cls.model_json_schema()

    def get_runtime_value(self, name: str) -> Any:
        """
        Get the runtime value for a specific field from the model instance.
        This is different from __getattr__ which returns the original schema objects.
        """
        self._assert_built()
        with self._lock:
            return getattr(self._model_instance, name)


# ────────────────────────────────────────────────────────────
#  Root node – QiSettings
# ────────────────────────────────────────────────────────────
class QiSettings(QiGroup):
    """
    Root-level group.  Acts as a context manager; on exit it auto-invokes build().
    """

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        super().__exit__(exc_type, exc_val, exc_tb)
        self.build()
