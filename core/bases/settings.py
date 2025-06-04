# core/bases/settings.py

from __future__ import annotations

import threading
from typing import Any, Union


class QiSetting:
    """
    Wraps a single "leaf" setting: a default value plus optional UI metadata.

    Supports:
      - __getattr__ / __setattr__ routing into a hidden sub-schema node if nested usage
      - explicit errors if someone tries to use it before it's been attached into a QiSettingsNode
      - context-manager support so that 'with some_node.setting:' pushes you into the child node
      - set_defaults(...) to push override entries into the shared defaults root

    Internally, every QiSetting carries:
      - 'default': the default value (scalar or collection)
      - 'label': an optional human label (if omitted, inferred from the Python variable name)
      - 'extra': a dict[str, Any] of arbitrary UI metadata (e.g. "choices", "enabled_by", etc.)
      - '_parent_node': once attached, points to the QiSettingsNode under which this leaf lives
      - '_key_in_parent': the name of this setting under its parent node
      - '_schema_node': if someone does 'some_setting.foo = …', we'll create a hidden QiSettingsNode
                        to hold those nested definitions. (In practice, most nesting happens under QiSettingsNode.)
    """

    default: Any
    label: str | None
    extra: dict[str, Any]
    _parent_node: "QiSettingsNode" | None
    _key_in_parent: str | None
    _schema_node: "QiSettingsNode" | None

    __slots__ = (
        "default",
        "label",
        "extra",
        "_parent_node",
        "_key_in_parent",
        "_schema_node",
    )

    def __init__(
        self,
        default: Any,
        *,
        label: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        # Assign payload:
        object.__setattr__(self, "default", default)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "extra", extra or {})

        # Not yet attached into any QiSettingsNode:
        object.__setattr__(self, "_parent_node", None)
        object.__setattr__(self, "_key_in_parent", None)
        object.__setattr__(self, "_schema_node", None)

    def __repr__(self) -> str:
        return (
            f"QiSetting(default={self.default!r}, "
            f"label={self.label!r}, extra={self.extra!r})"
        )

    # ─── I M P O R T A N T:  A T T A C H M E N T   W A R N I N G ───────────────
    #
    # Until this QiSetting has been inserted into a QiSettingsNode,
    # _parent_node is None; we must refuse any __getattr__, __setattr__, __enter__.
    def _ensure_attached(self) -> None:
        """
        Raise if this QiSetting is not yet inserted under a QiSettingsNode.
        """
        if self._parent_node is None:
            raise RuntimeError(
                f"QiSetting({self._key_in_parent!r}) is not attached to a QiSettingsNode. "
                "Assign it under a node before using nested/context features."
            )

    def __getattr__(self, item: str) -> Any:
        """
        Route unknown attribute lookups into a hidden sub-schema node.
        (Only valid after attachment.)
        """
        self._ensure_attached()
        if self._schema_node is None:
            # Create a hidden QiSettingsNode under the same defaults root
            defaults_root = self._parent_node._defaults_root
            hidden = QiSettingsNode(
                _parent=self._parent_node,
                _key_in_parent=self._key_in_parent,
                _defaults_root=defaults_root,
            )
            object.__setattr__(self, "_schema_node", hidden)
        return getattr(self._schema_node, item)

    def __setattr__(self, item: str, value: Any) -> None:
        """
        If assigning to one of our own slots, do it normally; otherwise,
        route into a hidden QiSettingsNode subtree (creating it if needed).
        """
        if item in QiSetting.__slots__:
            object.__setattr__(self, item, value)
            return

        # Otherwise, it's a nested assignment -> delegate to _schema_node
        self._ensure_attached()
        if self._schema_node is None:
            defaults_root = self._parent_node._defaults_root
            hidden = QiSettingsNode(
                _parent=self._parent_node,
                _key_in_parent=self._key_in_parent,
                _defaults_root=defaults_root,
            )
            object.__setattr__(self, "_schema_node", hidden)

        setattr(self._schema_node, item, value)

    def __enter__(self) -> QiSettingsNode:
        """
        Context-manager support: 'with some_leaf as node:' returns the hidden schema node.
        """
        self._ensure_attached()
        if self._schema_node is None:
            defaults_root = self._parent_node._defaults_root
            hidden = QiSettingsNode(
                _parent=self._parent_node,
                _key_in_parent=self._key_in_parent,
                _defaults_root=defaults_root,
            )
            object.__setattr__(self, "_schema_node", hidden)
        return self._schema_node

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # No special teardown
        return None

    def set_defaults(self, entry: Any) -> None:
        """
        For list/dict leaves, push 'entry' into the parallel defaults tree under this leaf's path.
        E.g. if this setting's full path is ("advanced","profiles"), then:
            defaults_root._children_defaults["advanced"]["profiles"] = entry
        """
        self._ensure_attached()
        parent = self._parent_node

        # Walk upward from _parent_node (QiSettingsNode) via _key_in_parent to build full leaf path:
        path: list[str] = []
        node_schema = parent
        while node_schema is not None and node_schema._key_in_parent is not None:
            path.append(node_schema._key_in_parent)
            node_schema = node_schema._parent
        path.reverse()
        path.append(self._key_in_parent)  # leaf's own key at the end

        # Now traverse the root defaults tree to set the override
        dnode = parent._defaults_root
        for segment in path[:-1]:
            if segment not in dnode._children_defaults or not isinstance(
                dnode._children_defaults.get(segment), dict
            ):
                dnode._children_defaults[segment] = {}
            dnode = dnode._children_defaults[segment]
        last_key = path[-1]
        dnode._children_defaults[last_key] = entry


class QiSettingsNode:
    """
    A tree-node for building a nested settings-schema.  Each child can be either:
      - QiSetting (a leaf, holding default + metadata)
      - QiSettingsNode (a nested group)

    Tracks in __slots__:
      - '_children_schema': mapping name->(QiSettingsNode or QiSetting)
      - '_children_defaults': parallel mapping name->runtime-default or subtree
      - '_parent': parent QiSettingsNode (None at root)
      - '_key_in_parent': the key under which this node lives in its parent
      - '_defaults_root': reference to the single "root of roots" defaults-tree
      - '_lock': threading.RLock for thread-safe mutations
    """

    _children_schema: dict[str, QiSettingsNode | QiSetting]
    _children_defaults: dict[str, Any]
    _parent: QiSettingsNode | None
    _key_in_parent: str | None
    _defaults_root: QiSettingsNode
    _lock: threading.RLock

    __slots__ = (
        "_children_schema",
        "_children_defaults",
        "_parent",
        "_key_in_parent",
        "_defaults_root",
        "_lock",
    )

    def __init__(
        self,
        *,
        _parent: QiSettingsNode | None = None,
        _key_in_parent: str | None = None,
        _defaults_root: QiSettingsNode | None = None,
    ) -> None:
        object.__setattr__(self, "_children_schema", {})
        object.__setattr__(self, "_children_defaults", {})

        object.__setattr__(self, "_parent", _parent)
        object.__setattr__(self, "_key_in_parent", _key_in_parent)

        # If no '_defaults_root' provided, this node is its own root:
        if _defaults_root is None:
            object.__setattr__(self, "_defaults_root", self)
        else:
            object.__setattr__(self, "_defaults_root", _defaults_root)

        # Thread-safe lock for schema/defaults mutations
        object.__setattr__(self, "_lock", threading.RLock())

    def __repr__(self) -> str:
        if self._parent is None:
            return "<QiSettingsNode ROOT>"
        return f"<QiSettingsNode .{self._key_in_parent!r}>"

    #
    # ─── Attribute Access / Creation ───────────────────────────────────────────
    #
    def __getattr__(self, item: str) -> Any:
        """
        If 'item' not in '_children_schema', create a new sub-node and return it.
        Prevent accessing private names directly.
        """
        if item.startswith("_"):
            raise AttributeError(f"{type(self).__name__!r} has no attribute {item!r}")
        with self._lock:
            if item not in self._children_schema:
                child = QiSettingsNode(
                    _parent=self,
                    _key_in_parent=item,
                    _defaults_root=self._defaults_root,
                )
                self._children_schema[item] = child
            return self._children_schema[item]

    def __setattr__(self, item: str, value: Any) -> None:
        """
        Assigning to a "public" attribute means:
          - If 'value' is QiSettingsNode: attach it under '_children_schema'.
          - If 'value' is QiSetting: attach it (and set its parent pointers).
          - Otherwise: wrap 'value' in QiSetting(default=value) and attach.
        """
        if item in QiSettingsNode.__slots__:
            object.__setattr__(self, item, value)
            return

        with self._lock:
            # Already-constructed sub-node?
            if isinstance(value, QiSettingsNode):
                node: QiSettingsNode = value
                object.__setattr__(node, "_parent", self)
                object.__setattr__(node, "_key_in_parent", item)
                object.__setattr__(node, "_defaults_root", self._defaults_root)
                self._children_schema[item] = node

            elif isinstance(value, QiSetting):
                leaf: QiSetting = value
                object.__setattr__(leaf, "_parent_node", self)
                object.__setattr__(leaf, "_key_in_parent", item)
                # (leaf._schema_node remains None until any nested assignment)
                self._children_schema[item] = leaf

            else:
                # Raw Python value -> auto-wrap into QiSetting
                leaf = QiSetting(default=value)
                object.__setattr__(leaf, "_parent_node", self)
                object.__setattr__(leaf, "_key_in_parent", item)
                self._children_schema[item] = leaf

    def __enter__(self) -> QiSettingsNode:
        """
        Context-manager support: 'with some_node as sub:' allows writing 'sub.foo = …'.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    #
    # ─── set_defaults ──────────────────────────────────────────────────────────
    #
    def set_defaults(self, data: Union[dict[str, Any], list[Any], Any]) -> None:
        """
        Bulk-set defaults at this node. If 'data' is a dict, merge its keys into
        '_children_defaults'; if it's anything else (e.g. list or primitive), replace
        '_children_defaults' entirely at this node.
        """
        with self._lock:
            if isinstance(data, dict):
                for k, v in data.items():
                    self._children_defaults[k] = v
            else:
                object.__setattr__(self, "_children_defaults", data)

    #
    # ─── Serialization (Schema vs. Values) ───────────────────────────────────
    #
    def get_schema(self) -> dict[str, Any]:
        """
        Recursively walk '_children_schema' to produce a pure-dict "schema":
          - QiSetting -> { "type": <typename>, "label": <label>, "extra": <extra>, ... }
          - QiSettingsNode -> nested dict
        """
        out: dict[str, Any] = {}
        with self._lock:
            for key, node in self._children_schema.items():
                if isinstance(node, QiSetting):
                    # Leaf: show type, label, extra metadata
                    out[key] = {
                        "type": type(node.default).__name__,
                        "label": node.label or key.capitalize(),
                        "extra": node.extra.copy(),
                    }
                    # If the QiSetting has a hidden sub-schema under '_schema_node', include it
                    if node._schema_node is not None:
                        out[key]["schema"] = node._schema_node.get_schema()
                else:
                    # Sub-node: recurse
                    out[key] = node.get_schema()
        return out

    def get_values(self) -> Any:
        """
        Recursively produce a "values-only" structure from '_children_defaults',
        falling back on each QiSetting.default when no override is present.
        """

        def _recurse_schema(node: QiSettingsNode, defaults: Any) -> Any:
            # If defaults at this level is not a dict, it's a leaf override (list or primitive)
            if not isinstance(defaults, dict):
                return defaults

            result: dict[str, Any] = {}
            for key, schema_node in node._children_schema.items():
                if key in defaults:
                    override = defaults[key]
                    if isinstance(schema_node, QiSetting):
                        result[key] = override
                    else:
                        result[key] = _recurse_schema(schema_node, override)
                else:
                    # No override: use schema default
                    if isinstance(schema_node, QiSetting):
                        result[key] = schema_node.default
                    else:
                        result[key] = _recurse_schema(schema_node, {})
                # If QiSetting has its own '_schema_node', merge nested children
                if isinstance(schema_node, QiSetting) and schema_node._schema_node:
                    nested = schema_node._schema_node.get_values()
                    if isinstance(result[key], dict) and isinstance(nested, dict):
                        result[key].update(nested)
                    else:
                        result[key] = nested
            return result

        with self._lock:
            return _recurse_schema(self, self._children_defaults)

    #
    # ─── Convenience Item-Access ───────────────────────────────────────────────
    #
    def __getitem__(self, key: str) -> Any:
        """
        Allow dict-style access: node["foo"] ↔ node.foo
        """
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Allow dict-style assignment: node["foo"] = value
        """
        setattr(self, key, value)

    #
    # ─── Iteration / Mapping-Style Support ────────────────────────────────────
    #
    def __iter__(self) -> Any:
        """
        Iterate over "current default values":
          - If get_values() is a dict, iterate over its values()
          - If it's a list, iterate over the list
          - Otherwise, empty iterator
        """
        data = self.get_values()
        if isinstance(data, dict):
            return iter(data.values())
        if isinstance(data, list):
            return iter(data)
        return iter(())

    def items(self) -> Any:
        """
        Return '.items()' if get_values() is a dict; else raise TypeError.
        """
        data = self.get_values()
        if isinstance(data, dict):
            return data.items()
        raise TypeError(f"{type(self).__name__} is not a mapping (no .items())")

    def keys(self) -> Any:
        """
        Return '.keys()' if get_values() is a dict; else raise TypeError.
        """
        data = self.get_values()
        if isinstance(data, dict):
            return data.keys()
        raise TypeError(f"{type(self).__name__} is not a mapping (no .keys())")

    def values(self) -> Any:
        """
        Return '.values()' if get_values() is a dict;
        if it's a list, return that list; else raise TypeError.
        """
        data = self.get_values()
        if isinstance(data, dict):
            return data.values()
        if isinstance(data, list):
            return data
        raise TypeError(
            f"{type(self).__name__} is not a mapping or sequence (no .values())"
        )
