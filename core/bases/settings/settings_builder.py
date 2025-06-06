# core/bases/settings/settings_builder.py

from __future__ import annotations

import copy
from typing import Annotated, Any, Type, get_args, get_origin

from pydantic import BaseModel, Field, ValidationError, create_model


class QiSettingsLeaf:
    """
    Represents a single "leaf" field in the settings tree:
      - 'name': the attribute name under its parent
      - 'annotation': the original Python type annotation (e.g. 'int', 'list[str]', etc.)
      - 'default': the default value (could be None if no default was specified)
      - 'metadata': a dict of UI/schema hints (e.g. choices, multi_select, title, description)
      - 'nested_node': if the annotation itself was something like Annotated[Tuple, {...}],
                       and that Annotated contained a nested QiSettingsNode, it will appear here.
    """

    __slots__ = ("name", "annotation", "default", "metadata", "nested_node")

    def __init__(
        self,
        name: str,
        annotation: Any,
        default: Any = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.name = name
        self.annotation = annotation
        self.default = default
        self.metadata = metadata or {}
        self.nested_node: QiSettingsNode | None = None  # for nested Annotated types

    def clone(self) -> QiSettingsLeaf:
        """
        Deep-copy this leaf's definition (schema plus default).  Nested node is cloned by the caller.
        """
        new_leaf = QiSettingsLeaf(
            name=self.name,
            annotation=self.annotation,
            default=copy.deepcopy(self.default),
            metadata=copy.deepcopy(self.metadata),
        )
        # NOTE: nested_node will be attached by the caller (deep copy logic)
        return new_leaf

    #
    # ─── Attach metadata to a leaf or node ─────────────────────────────────────
    #
    def meta(self, **kwargs: Any) -> QiSettingsNode | QiSettingsLeaf:
        """
        If called on a QiSettingsNode, merges kwargs into its metadata.
        If called on a QiSettingsLeaf, merges kwargs into its metadata.

        Returns self so you can call it in a single expression.
        """
        # This method should be attached to both QiSettingsNode and QiSettingsLeaf.
        # But in practice, we'll bind it dynamically so that 'node.foo.meta(...)'
        # works whether 'foo' is a QiSettingsNode or a leaf.
        raise NotImplementedError("Should be monkey-patched onto both Node and Leaf")


class QiSettingsNode:
    """
    A builder for nested settings.  Supports:
      - Declaring attributes via 'node.some_field: int = 5' or inside 'with node as n:' blocks
      - Attaching UI hints via 'node.some_field.meta(...)'
      - Inheriting an entire subtree via '.inherit(...)'
      - Overriding defaults via '.set_default(...)'
      - Emitting a Pydantic model via '.build_model()'
      - Producing JSON-schema and JSON-values via '.get_schema()' / '.get_values()'
    """

    __slots__ = (
        "_parent",
        "_name",
        "_children",
        "_children_defaults",
        "_metadata",
    )

    def __init__(
        self,
        *,
        parent: QiSettingsNode | None = None,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        # Who is my parent?  None if this is the root node.
        self._parent: QiSettingsNode | None = parent
        self._name: str | None = name

        # child_name → (QiSettingsLeaf or QiSettingsNode)
        self._children: dict[str, QiSettingsLeaf | QiSettingsNode] = {}

        # defaults overrides at this node; a dict mapping child_name → override_value
        self._children_defaults: dict[str, Any] = {}

        # metadata for this node itself (title, modifiable, list, etc.)
        self._metadata: dict[str, Any] = metadata or {}

    def __repr__(self) -> str:
        path = []
        node: QiSettingsNode | None = self
        while node is not None and node._name is not None:
            path.append(node._name)
            node = node._parent
        path = ".".join(reversed(path)) or "<root>"
        return f"<QiSettingsNode {path}>"

    #
    # ─── Context-manager support ─────────────────────────────────────────────────
    #
    def __enter__(self) -> QiSettingsNode:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # No special teardown required
        return None

    #
    # ─── Declare a new field or nested node ────────────────────────────────────
    #
    def __getattr__(self, item: str) -> Any:
        """
        If you write 'node.some_group' without having assigned it yet, this method creates
        a new nested QiSettingsNode on demand.
        """
        if item.startswith("_"):
            raise AttributeError(f"{type(self).__name__!r} has no attribute {item!r}")

        # If it's already declared, return it
        if item in self._children:
            return self._children[item]

        # Otherwise, create a new nested node (no defaults, no metadata yet)
        new_node = QiSettingsNode(parent=self, name=item)
        self._children[item] = new_node
        return new_node

    def __setattr__(self, item: str, value: Any) -> None:
        """
        When you assign to 'node.some_field = 123', one of two things happens:
          1. If 'item' is one of our internal slots, do a normal setattr.
          2. Otherwise, interpret as a leaf declaration: wrap it into QiSettingsLeaf.
        """
        slots = set(QiSettingsNode.__slots__)
        if item in slots:
            object.__setattr__(self, item, value)
            return

        # Otherwise, we are creating/re-assigning a leaf under 'self'
        # Extract the annotation (if any) and default from the plugin class's __annotations__
        #   (Note: In practice, the decorator has already bound __annotations__ for us.)
        annotation = None

        # If the assigned value is itself a QiSettingsNode or QiSettingsLeaf, attach directly
        if isinstance(value, QiSettingsNode):
            object.__setattr__(value, "_parent", self)
            object.__setattr__(value, "_name", item)
            self._children[item] = value
            return

        if isinstance(value, QiSettingsLeaf):
            leaf = value
            object.__setattr__(leaf, "name", item)
            leaf.nested_node = None
            self._children[item] = leaf
            return

        # Otherwise, wrap raw Python value into a QiSettingsLeaf
        # We need to get the annotation from self.__annotations__[item]
        # If plugin author used 'Meta[...]', that 'annotation' is already an Annotated[...] object.
        # For now, assume the decorator gave us a mapping of annotations in self.__annotations__.
        annotation = getattr(self, "__annotations__", {}).get(item, None)
        leaf = QiSettingsLeaf(
            name=item, annotation=annotation, default=value, metadata={}
        )
        self._children[item] = leaf

    #
    # ─── Attach metadata to a leaf or node ─────────────────────────────────────
    #
    def meta(self, **kwargs: Any) -> QiSettingsNode | QiSettingsLeaf:
        """
        If called on a QiSettingsNode, merges kwargs into its metadata.
        If called on a QiSettingsLeaf, merges kwargs into its metadata.

        Returns self so you can call it in a single expression.
        """
        # This method should be attached to both QiSettingsNode and QiSettingsLeaf.
        # But in practice, we'll bind it dynamically so that 'node.foo.meta(...)'
        # works whether 'foo' is a QiSettingsNode or a leaf.
        raise NotImplementedError("Should be monkey-patched onto both Node and Leaf")

    # def meta(self: QiSettingsNode, **kwargs: Any) -> QiSettingsNode:
    #     self._metadata.update(kwargs)
    #     return self

    #
    # ─── Override defaults (at any subtree) ───────────────────────────────────
    #
    def set_default(self, data: dict[str, Any] | list[Any] | Any) -> None:
        """
        Bulk-override defaults at this node.  If 'data' is a dict, merge keys into
        '_children_defaults'; otherwise, replace '_children_defaults' entirely.
        """
        if isinstance(data, dict):
            for k, v in data.items():
                self._children_defaults[k] = v
        else:
            # e.g. data is a list or scalar—treat the entire node as overridden
            self._children_defaults = data

    #
    # ─── Inherit (deep-copy) an entire subtree ─────────────────────────────────
    #
    def inherit(self, **overrides: Any) -> QiSettingsNode:
        """
        Return a brand-new QiSettingsNode whose schema & defaults are a deep-copy of self,
        then merge in any 'overrides' (metadata) at the new root.
        """

        def _deep_copy_node(
            src: QiSettingsNode, parent: QiSettingsNode | None, name: str | None
        ) -> QiSettingsNode:
            # 1) Make a fresh node with copied metadata
            new_meta = copy.deepcopy(src._metadata)
            new_node = QiSettingsNode(parent=parent, name=name, metadata=new_meta)

            # 2) Copy children_defaults
            new_node._children_defaults = copy.deepcopy(src._children_defaults)

            # 3) Recursively copy children (leaf vs. node)
            for child_name, child_val in src._children.items():
                if isinstance(child_val, QiSettingsNode):
                    # Recursively clone nested node
                    cloned_child = _deep_copy_node(child_val, new_node, child_name)
                    new_node._children[child_name] = cloned_child
                else:
                    # child_val is a QiSettingsLeaf → clone the leaf
                    orig_leaf: QiSettingsLeaf = child_val
                    cloned_leaf = orig_leaf.clone()
                    cloned_leaf.nested_node = None
                    # If the original leaf had a nested node (via Annotated), copy that too:
                    if orig_leaf.nested_node is not None:
                        cloned_subnode = _deep_copy_node(
                            orig_leaf.nested_node, new_node, child_name
                        )
                        cloned_leaf.nested_node = cloned_subnode
                    new_node._children[child_name] = cloned_leaf

            return new_node

        new_root = _deep_copy_node(self, parent=None, name=None)

        # 4) Apply any overrides to the new root's metadata
        new_root._metadata.update(overrides)
        return new_root

    #
    # ─── Build a Pydantic model from this node and its children ───────────────
    #
    def build_model(self, model_name: str = "SettingsModel") -> Type[BaseModel]:
        """
        Recursively constructs a Pydantic BaseModel class that mirrors this subtree's schema,
        applying type-hints, defaults, and JSON-schema metadata as Field(...).
        """
        fields: dict[str, tuple[Any, Any]] = {}
        submodels: dict[str, Type[BaseModel]] = {}

        for child_name, child_val in self._children.items():
            # 1) If child is a nested QiSettingsNode, build a submodel class for it
            if isinstance(child_val, QiSettingsNode):
                submodel = child_val.build_model(
                    model_name=f"{model_name}_{child_name}"
                )
                submodels[child_name] = submodel

                # Extract default if any
                default_override = self._children_defaults.get(child_name, ...)
                fields[child_name] = (submodel, default_override)

            else:
                # child_val is a QiSettingsLeaf
                leaf: QiSettingsLeaf = child_val

                # Determine Pydantic type from leaf.annotation
                ann = leaf.annotation
                default_override = self._children_defaults.get(child_name, leaf.default)

                # Build Field(..., description=..., title=..., etc.) from leaf.metadata
                field_kwargs: dict[str, Any] = {}
                if "title" in leaf.metadata:
                    field_kwargs["title"] = leaf.metadata["title"]
                if "description" in leaf.metadata:
                    field_kwargs["description"] = leaf.metadata["description"]
                if "choices" in leaf.metadata:
                    field_kwargs["enum"] = leaf.metadata["choices"]
                if "multi_select" in leaf.metadata and leaf.metadata["multi_select"]:
                    # If multi_select on a list of strings, Pydantic will enforce allowed values
                    # via a validator or via JSON-schema. We rely on JSON-schema here:
                    # (the UI can read it from the schema). No extra code needed at runtime.
                    pass

                # If this leaf's annotation is an Annotated[base, metadata], unwrap:
                origin = get_origin(ann)
                if origin is Annotated:
                    base_type, *annot_args = get_args(ann)
                    # We assume the last Annotated argument is a dict of metadata
                    if annot_args and isinstance(annot_args[-1], dict):
                        field_kwargs.update(annot_args[-1])
                    ann = base_type

                # Now define the Pydantic field:
                try:
                    fields[child_name] = (ann, Field(default_override, **field_kwargs))
                except TypeError:
                    # Fallback in case Field(...) keys don't match
                    fields[child_name] = (ann, default_override)

        # Create the model, including any nested submodels:
        model = create_model(model_name, __base__=BaseModel, **fields)

        # Attach any nested submodels as attributes so Pydantic can resolve them
        for name, submodel in submodels.items():
            setattr(model, name, (submodel, ...))  # type: ignore

        return model

    #
    # ─── Extract JSON-schema from the built Pydantic model ─────────────────────
    #
    def get_schema(self) -> dict[str, Any]:
        """
        Build a Pydantic model and then call .model_json_schema() to get the JSON-schema.
        """
        try:
            model_cls = self.build_model(model_name="TempSchemaModel")
            return model_cls.model_json_schema(by_alias=True)
        except (ValidationError, TypeError):
            # If building fails (e.g. missing defaults on tuples), return a minimal fallback
            return {}

    #
    # ─── Extract “values” (merged defaults + overrides) ─────────────────────────
    #
    def get_values(self) -> dict[str, Any]:
        """
        Instantiate the built Pydantic model (so that defaults + overrides are applied)
        and then call .model_dump() to get a plain-dict of values.
        """
        model_cls = self.build_model(model_name="TempValuesModel")
        try:
            instance = model_cls()  # validate defaults
            return instance.model_dump()
        except ValidationError:
            return {}


# ————————————————————————————————————————————————————————————
# Monkey-patch the .meta(...) method onto both QiSettingsNode and QiSettingsLeaf
# so that in user code you can always call '.meta(...)' on either.
# ————————————————————————————————————————————————————————————


def _node_meta(self: QiSettingsNode, **kwargs: Any) -> QiSettingsNode:
    self._metadata.update(kwargs)
    return self


def _leaf_meta(self: QiSettingsLeaf, **kwargs: Any) -> QiSettingsLeaf:
    self.metadata.update(kwargs)
    return self


# Attach them:
QiSettingsNode.meta = _node_meta  # type: ignore
QiSettingsLeaf.meta = _leaf_meta  # type: ignore
