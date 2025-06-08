from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model


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
        default: int | str | float | bool
        | list[Any] | tuple[Any] | set[Any] | None = None,
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
    def set_meta(self, **kwargs: Any) -> None:
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
        info.update(self._meta)
        return info

    def _signature(self) -> str:
        return (
            "PROP|"
            f"{type(self.default).__name__}|"
            f"{repr(sorted(self._meta.items()))}"
        )


# ────────────────────────────────────────────────────────────
#  QiGroup – interior node
# ────────────────────────────────────────────────────────────
class QiGroup:
    """
    Group node.

    Collection shape rules
    ----------------------
    - list_mode=True                → list[SubModel]               (no default_key allowed)
    - default_key="name"            → dict[str,SubModel], first entry "name"
    - neither list_mode nor key set → dict[str,SubModel], first entry "_auto"
    """

    # ------------ construction ------------ #
    def __init__(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        list_mode: bool | None = None,
        default_key: str | None = None,
        **kwargs: Any,
    ):
        if list_mode and default_key:
            raise ValueError("list_mode=True conflicts with default_key")

        if list_mode is None:
            list_mode = False                         # mapping by default
        self.list_mode: bool = bool(list_mode)
        self._default_key_hint: str | None = default_key

        self.title = title
        self.description = description
        self._meta: dict[str, Any] = kwargs.copy()

        # definition-time data
        self._children: dict[str, QiProp | "QiGroup"] = {}
        self._defaults: dict[str, Any] = {}
        self._parent: QiGroup | None = None
        self._parent_key: Optional[str] = None

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
            **deepcopy(self._meta, memo),
        )
        clone._defaults = deepcopy(self._defaults, memo)
        clone._lock = RLock()
        for name, child in self._children.items():
            cpy = deepcopy(child, memo)
            if isinstance(cpy, QiGroup):
                cpy._parent = clone
                cpy._parent_key = name
            clone._children[name] = cpy
        memo[id(self)] = clone
        return clone

    # --------------- context manager --------------- #
    def __enter__(self) -> "QiGroup":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # snapshot default entry for mapping groups if none supplied
        if not self.list_mode and not self._defaults:
            key = self._default_key_hint or "_auto"
            self._defaults = {key: {}}

    # --------------- attribute plumbing --------------- #
    def __getattr__(self, name: str) -> Any:
        if self._model_instance is not None:
            with self._lock:
                return getattr(self._model_instance, name)
        if name in self._children:
            return self._children[name]
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        internals = {
            "title", "description", "_meta",
            "_children", "_defaults", "_parent", "_parent_key",
            "_model_cls", "_model_instance", "_lock",
            "list_mode", "_default_key_hint",
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
    def set_meta(self, **kwargs: Any) -> None:
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
        self._default_key_hint = key

    def set_defaults(self, values: dict[str, Any]) -> None:
        """
        Merge *values* into the defaults under this subtree and rebuild the
        root model so changes are visible immediately.
        """
        with self._lock:
            self._defaults = deepcopy(values)
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
            clone._defaults = {}
        return clone

    # ------------- defaults machinery ------------- #
    def _apply_defaults(self) -> None:
        for k, override in deepcopy(self._defaults).items():
            ch = self._children.get(k)
            if isinstance(ch, QiProp) and not isinstance(ch, QiGroup):
                ch.default = override
            elif isinstance(ch, QiGroup):
                ch._defaults = deepcopy(override)
                ch._apply_defaults()
        self._defaults = {}
        for c in self._children.values():
            if isinstance(c, QiGroup):
                c._apply_defaults()

    # ---------------- helpers ---------------- #
    def _find_root(self) -> "QiGroup":
        node: QiGroup = self
        while node._parent is not None:
            node = node._parent
        return node

    def _signature(self) -> str:
        parts = []
        for nm, child in sorted(self._children.items()):
            if isinstance(child, QiGroup):
                parts.append((
                    "G", nm, child._signature(),
                    repr(sorted(child._meta.items())),
                    child.list_mode,
                    child._default_key_hint,
                ))
            else:
                parts.append(("P", nm, child._signature()))
        return (
            repr(parts) + "|"
            + repr(sorted(self._meta.items())) + "|"
            + str(self.list_mode) + "|"
            + repr(self._default_key_hint)
        )

    # ------------- model building ------------- #
    def _build_model(
        self, name: str, cache: Dict[str, type[BaseModel]]
    ) -> type[BaseModel]:
        sig = self._signature()
        if sig in cache:
            return cache[sig]

        self._apply_defaults()
        fields: dict[str, tuple[Any, Any]] = {}

        for nm, child in self._children.items():
            if isinstance(child, QiProp) and not isinstance(child, QiGroup):
                default = child.default
                if isinstance(default, (list, tuple, set)):
                    kinds = {type(x) for x in default}
                    if len(kinds) > 1:
                        raise TypeError("heterogeneous list/tuple/set defaults")
                    inner = kinds.pop() if default else Any
                    ann: Any = list[inner]
                else:
                    ann = type(default) if default is not None else Any
                fields[nm] = (ann, Field(**child._field_info()))
            else:
                sub_cls = child._build_model(nm.capitalize() + "Model", cache)
                meta = child._meta.copy()
                if child.title is not None:
                    meta.setdefault("title", child.title)
                if child.description is not None:
                    meta.setdefault("description", child.description)
                if child.list_mode:
                    ann = list[sub_cls]
                    field = Field(default_factory=list, **meta)
                else:
                    ann = dict[str, sub_cls]
                    field = Field(default_factory=dict, **meta)
                fields[nm] = (ann, field)

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
            cache: Dict[str, type[BaseModel]] = {}
            self._model_cls = self._build_model(self.title or "RootModel", cache)
            self._model_instance = self._model_cls(**{})

    # -------------- read helpers ------------- #
    def _assert_built(self) -> None:
        if self._model_instance is None:
            raise RuntimeError(
                "Settings not built yet. "
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