# core/bases/settings.py

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model


# ────────────────────────────────────────────────────────────
#  Schema simplifier
# ────────────────────────────────────────────────────────────
def _simplify_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Collapse structurally identical $defs entries so that the final JSON schema
    is smaller and diff-friendly.

    Two definitions are considered identical when their ``properties`` sections
    are equal once the presentational keys ``default``, ``title`` and
    ``description`` are stripped.
    """
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        return schema

    # Bucket definitions by structural signature
    buckets: dict[str, list[str]] = {}
    for name, sub in defs.items():
        stripped = {
            p: {
                k: v
                for k, v in d.items()
                if k not in {"default", "title", "description"}
            }
            for p, d in sub.get("properties", {}).items()
        }
        sig = repr(sorted(stripped.items()))
        buckets.setdefault(sig, []).append(name)

    # Map non-canonical names → canonical name
    mapping: dict[str, str] = {}
    for names in buckets.values():
        canon = min(names, key=lambda n: (len(n), n))
        for n in names:
            if n != canon:
                mapping[f"#/$defs/{n}"] = f"#/$defs/{canon}"

    # Rewrite $ref links
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if (r := node.get("$ref")) in mapping:
                node["$ref"] = mapping[r]
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    result = deepcopy(schema)
    walk(result)

    # Keep only canonical definitions
    result["$defs"] = {
        min(lst, key=len): defs[min(lst, key=len)] for lst in buckets.values()
    }
    return result


# ────────────────────────────────────────────────────────────
#  QiProp – leaf node
# ────────────────────────────────────────────────────────────
class QiProp:
    """
    Leaf-level setting.

    Parameters
    ----------
    default
        Default Python value (scalar, list, tuple or set).
    title, description
        Optional short text used by UIs.
    **kwargs
        Any extra key–value pairs are preserved verbatim in ``_meta`` and
        forwarded into :pyfunc:`pydantic.Field`.  Use them for UI hints such as
        ``choices``, ``step``, ``icon``…

    Notes
    -----
    Call :pyfunc:`set_meta` to mutate or extend metadata after creation.
    """

    # ── construction ───────────────────────────────────────
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

    # ── public helpers ─────────────────────────────────────
    def set_meta(self, **kwargs: Any) -> None:
        """
        Update built-in attributes and/or extend arbitrary metadata::

            prop.set_meta(title="Threshold", min=0, max=1)
        """
        for k, v in kwargs.items():
            if k in {"default", "title", "description"}:
                setattr(self, k, v)
            else:
                self._meta[k] = v

    # ── internal helper for Pydantic ───────────────────────
    def _field_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {"default": self.default}
        if self.title is not None:
            info["title"] = self.title
        if self.description is not None:
            info["description"] = self.description
        info.update(self._meta)
        return info


# ────────────────────────────────────────────────────────────
#  QiGroup – interior node
# ────────────────────────────────────────────────────────────
class QiGroup:
    """
    Grouping node that can contain other groups or props.

    • Accepts arbitrary keyword metadata stored in ``_meta``.
    • Before :pyfunc:`build`, attribute access mutates the schema; afterwards it
      proxies to the live Pydantic instance with full validation.
    """

    # ── construction ───────────────────────────────────────
    def __init__(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        **kwargs: Any,
    ):
        self.title = title
        self.description = description
        self._meta: dict[str, Any] = kwargs.copy()

        # definition-time state
        self._children: dict[str, QiProp | "QiGroup"] = {}
        self._defaults: dict[str, Any] = {}
        self._parent: QiGroup | None = None

        # run-time state
        self._model_cls: type[BaseModel] | None = None
        self._model_instance: BaseModel | None = None
        self._cached_schema: dict[str, Any] | None = None
        self._lock = RLock()

    # ── deepcopy support for inherit() ─────────────────────
    def __deepcopy__(self, memo: dict[int, Any]) -> "QiGroup":
        cls = type(self)
        clone = cls(
            title=self.title, description=self.description, **deepcopy(self._meta, memo)
        )

        clone._defaults = deepcopy(self._defaults, memo)
        clone._lock = RLock()  # fresh lock
        clone._model_cls = None
        clone._model_instance = None
        clone._cached_schema = None

        for name, child in self._children.items():
            copied = deepcopy(child, memo)
            if isinstance(copied, QiGroup):
                copied._parent = clone
            clone._children[name] = copied

        memo[id(self)] = clone
        return clone

    # ── context manager (definition stage) ─────────────────
    def __enter__(self) -> "QiGroup":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    # ── attribute plumbing ─────────────────────────────────
    def __getattr__(self, name: str) -> Any:
        if self._model_instance is not None:
            with self._lock:
                return getattr(self._model_instance, name)

        if name in self._children:
            return self._children[name]

        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        internals = {
            "title",
            "description",
            "_meta",
            "_children",
            "_defaults",
            "_parent",
            "_model_cls",
            "_model_instance",
            "_cached_schema",
            "_lock",
        }
        if name in internals or name.startswith("_"):
            object.__setattr__(self, name, value)
            return

        if self._model_instance is not None:  # run-time
            with self._lock:
                setattr(self._model_instance, name, value)
            return

        # definition-time
        if isinstance(value, QiGroup):
            value._parent = self
            self._children[name] = value
        elif isinstance(value, QiProp):
            self._children[name] = value
        else:
            self._children[name] = QiProp(value)

    # ── public helpers ─────────────────────────────────────
    def set_meta(self, **kwargs: Any) -> None:
        """Mutate or extend metadata on this group node."""
        with self._lock:
            for k, v in kwargs.items():
                if k in {"title", "description"}:
                    setattr(self, k, v)
                else:
                    self._meta[k] = v

    def set_defaults(self, values: dict[str, Any]) -> None:
        """
        Override default values below this node **and** trigger a rebuild of
        the root model so that subsequent reads see the change.
        """
        with self._lock:
            self._defaults = deepcopy(values)
            self._find_root().build()

    def inherit(self) -> "QiGroup":
        """
        Return a **deep copy** of this subtree, detached from the original
        parent.  Useful when you need two similar branches with diverging
        defaults or metadata.
        """
        with self._lock:
            return deepcopy(self)

    # ── defaults machinery ─────────────────────────────────
    def _apply_defaults(self) -> None:
        for key, override in deepcopy(self._defaults).items():
            child = self._children.get(key)
            if isinstance(child, QiProp) and not isinstance(child, QiGroup):
                child.default = override
            elif isinstance(child, QiGroup):
                child._defaults = deepcopy(override)
                child._apply_defaults()
        self._defaults = {}
        for c in self._children.values():
            if isinstance(c, QiGroup):
                c._apply_defaults()

    # ── helpers ────────────────────────────────────────────
    def _find_root(self) -> "QiGroup":
        node: QiGroup = self
        while node._parent is not None:
            node = node._parent
        return node

    # ── model building ─────────────────────────────────────
    def _build_model(self, name: str) -> type[BaseModel]:
        self._apply_defaults()
        fields: dict[str, tuple[Any, Any]] = {}

        for nm, child in self._children.items():
            # ---------- leaf ----------
            if isinstance(child, QiProp) and not isinstance(child, QiGroup):
                default = child.default

                if isinstance(default, (list, tuple, set)):
                    kinds = {type(x) for x in default}
                    if len(kinds) > 1:
                        raise TypeError(
                            "list / tuple / set defaults must be homogeneous"
                        )
                    inner = kinds.pop() if default else Any
                    ann: Any = list[inner]  # lists are JSON-serialisable
                else:
                    ann = type(default) if default is not None else Any

                fields[nm] = (ann, Field(**child._field_info()))

            # ---------- subgroup ----------
            else:
                sub_cls = child._build_model(nm.capitalize() + "Model")

                subgroup_meta = child._meta.copy()
                if child.title is not None:
                    subgroup_meta.setdefault("title", child.title)
                if child.description is not None:
                    subgroup_meta.setdefault("description", child.description)

                fields[nm] = (sub_cls, Field(default_factory=sub_cls, **subgroup_meta))

        return create_model(
            name,
            __config__=ConfigDict(validate_assignment=True),
            **fields,  # type: ignore[arg-type]
        )

    def build(self) -> None:
        """
        Build / rebuild the whole Pydantic model tree starting from the root
        ``QiSettings``. Automatically called when the root with-block exits.
        """
        with self._lock:
            if not isinstance(self, QiSettings):
                raise RuntimeError("Only QiSettings may build; call on root QiSettings")
            cls = self._build_model(self.title or "RootModel")
            self._model_cls = cls
            self._model_instance = cls(**{})
            self._cached_schema = None

    # ── public read API ────────────────────────────────────
    def get_values(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict of the current setting values."""
        with self._lock:
            if self._model_instance is None:
                raise RuntimeError("must build() first")
            return self._model_instance.model_dump()

    def get_raw_schema(self) -> dict[str, Any]:
        """Return the raw Pydantic JSON schema (no deduplication)."""
        with self._lock:
            if self._model_cls is None:
                raise RuntimeError("must build() first")
            return self._model_cls.model_json_schema()

    def get_schema(self) -> dict[str, Any]:
        """Return a simplified JSON schema with duplicate ``$defs`` merged."""
        with self._lock:
            if self._cached_schema is None:
                self._cached_schema = _simplify_schema(self.get_raw_schema())
            return self._cached_schema


# ────────────────────────────────────────────────────────────
#  Root node – QiSettings
# ────────────────────────────────────────────────────────────
class QiSettings(QiGroup):
    """
    Root-level group.  Used as a context manager::

        with QiSettings() as settings:
            settings.foo = 1
            ...

    Upon leaving the with-block it auto-invokes :pyfunc:`build`, producing the
    live Pydantic model instance so that reads/writes happen with validation.
    """

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        super().__exit__(exc_type, exc_val, exc_tb)
        self.build()
