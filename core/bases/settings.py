# core/bases/settings.py

from __future__ import annotations

from copy import deepcopy
from typing import Any, Type

from pydantic import BaseModel, Field, create_model


class QiProp:
    """
    Wraps a default value + optional metadata (title/description/choices/etc.).
    Internally, this generates Pydantic Field(...) arguments when building the model.
    """

    default: int | str | float | bool | list[int | str | float] | None
    title: str | None
    description: str | None
    choices: list[Any] | None
    multi_select: bool
    _extra: dict[str, Any]

    __slots__ = (
        "default",
        "title",
        "description",
        "choices",
        "multi_select",
        "_extra",
    )

    def __init__(
        self,
        default: int | str | float | bool | list[int | str | float] | None = None,
        *,
        title: str | None = None,
        description: str | None = None,
        choices: list[Any] | None = None,
        multiselect: bool = False,
        **kwargs,
    ):
        self.default = default
        self.title = title
        self.description = description
        self.choices = choices
        self.multi_select = multiselect
        self._extra: dict[str, Any] = dict()

    def specs(self, **kwargs: Any) -> None:
        """
        Post-creation metadata editing. E.g.:
        p = QiProp(3, title="Age")
        p.specs(description="User's age", choices=[18, 21, 30])
        """
        for key, value in kwargs.items():
            if key in self.__slots__:
                setattr(self, key, value)
            else:
                self._extra[key] = value

    def _field_info(self, annotation: Any) -> dict[str, Any]:
        """
        Convert this QiProp into a dict of kwargs for Pydantic's Field():
        E.g., {"default": self.default, "title": ..., "description": ..., "enum": [...]}.
        """
        info: dict[str, Any] = {"default": self.default}
        if self.title is not None:
            info["title"] = self.title
        if self.description is not None:
            info["description"] = self.description
        if self.choices is not None:
            info["enum"] = self.choices
        if self.multi_select:
            # Pass x_multi_select so it appears in model_json_schema()
            info["x_multi_select"] = True
        info.update(self._extra)

        return info


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
    'self.settings' is a Pydantic instance with real attributes, giving dot-notation
    and full linter support.
    """

    _children: dict[str, Any]
    title: str | None
    description: str | None
    modifiable: bool
    list_mode: bool
    _defaults: dict[str, Any]
    _parent: QiGroup | None
    _model_cls: Type[BaseModel]
    _model_instance: BaseModel

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
        title: str | None = None,
        description: str | None = None,
        modifiable: bool = False,
        list: bool = False,
        **kwargs,
    ):
        object.__setattr__(self, "_children", dict())
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "modifiable", modifiable)
        object.__setattr__(self, "list_mode", list)
        object.__setattr__(self, "_defaults", dict())
        object.__setattr__(self, "_parent", None)
        # _model_cls and _model_instance get set by @define_settings later

    def __getattr__(self, name: str) -> Any:
        """
        Forward missing-attribute lookups into self._children.
        Enables 'with s.internal_profiles as p:' after 's.internal_profiles = QiGroup()'.
        """
        if name in self._children:
            return self._children[name]
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r}"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Capture 's.name = value' inside the 'with'-block:
        - QiGroup → register child group
        - QiProp → register leaf with metadata
        - Otherwise wrap in QiProp(default=value)
        Stored in self._children; no direct __dict__ assignment.
        """
        if name in self.__slots__:
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
        without triggering __getattr__. Recursively deep-copy nested QiGroups/QiProps.
        """
        cls = type(self)
        new_group = cls(
            title=self.title,
            description=self.description,
            modifiable=self.modifiable,
            list=self.list_mode,
        )
        object.__setattr__(new_group, "_defaults", deepcopy(self._defaults, memo))

        new_children: dict[str, Any] = {}
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
        Store override-defaults that will be applied when building the Pydantic model.
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
        for key, value in kwargs.items():
            match key:
                case "title":
                    object.__setattr__(self, "title", value)
                case "description":
                    object.__setattr__(self, "description", value)
                case "modifiable":
                    object.__setattr__(self, "modifiable", value)
                case "list":
                    object.__setattr__(self, "list_mode", value)
                case _:
                    setattr(self, key, value)

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
        fields_def: dict[str, Any] = {}

        # Process field definitions
        for name, child in self._children.items():
            if isinstance(child, QiProp):
                py_default = child.default
                annotation = type(py_default) if py_default is not None else Any
                if isinstance(py_default, list):
                    if py_default:
                        element_type = type(py_default[0])
                        annotation = list[element_type]  # e.g. list[int] or list[str]
                    else:
                        annotation = list[Any]
                field_kwargs = child._field_info(annotation)
                fields_def[name] = (annotation, Field(**field_kwargs))
            else:
                nested_model = child._build_model(
                    model_name=name.capitalize() + "Model"
                )
                nested_default = nested_model(**{})
                fields_def[name] = (nested_model, Field(default=nested_default))

        # Create the model class
        model_class = create_model(
            model_name,
            **fields_def,  # type: ignore[arg-type]
        )

        # Set model_config after model creation
        model_class.model_config = {"validate_assignment": True}

        return model_class

    def model_dump(self) -> dict[str, Any]:
        if not hasattr(self, "_model_cls"):
            raise RuntimeError("You must call define_settings first.")
        return self._model_cls.model_dump()

    def model_json_schema(self) -> dict[str, Any]:
        """
        After @define_settings, returns the Pydantic model's JSON-schema as a dict.
        """
        if not hasattr(self, "_model_cls"):
            raise RuntimeError("You must call define_settings first.")
        return self._model_cls.model_json_schema()

    def _attach_model(self, model_class: Type[BaseModel]) -> None:
        """
        Called by @define_settings: store the Pydantic model class and a default instance.
        """
        object.__setattr__(self, "_model_cls", model_class)
        default_instance = model_class(**{})  # fill in defaults
        object.__setattr__(self, "_model_instance", default_instance)


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
                print(self.settings.model_json_schema())

    What it does:
    1) Grabs 'MyPlugin.settings' (a QiGroup), builds a Pydantic model from its _children.
    2) Attaches the model class to the QiGroup as _model_cls and a template instance as _model_instance.
    3) Replaces MyPlugin.__init__ so that on instantiation, 'self.settings' becomes a deepcopy of the template instance.
    4) Adds helper methods 'model_json_schema()' and 'settings_dict()' to MyPlugin.
    """

    def decorator(plugin_class: Type[Any]) -> Type[Any]:
        if not hasattr(plugin_class, root_name):
            raise AttributeError(
                f"{plugin_class.__name__} has no '{root_name}' attribute"
            )

        group = getattr(plugin_class, root_name)
        if not isinstance(group, QiGroup):
            raise TypeError(f"'{root_name}' must be a QiGroup instance")

        # Build the Pydantic model from the QiGroup tree
        model_class = group._build_model(model_name=root_name.capitalize() + "Model")
        group._attach_model(model_class)

        orig_init = getattr(plugin_class, "__init__", None)

        def __init__(self, *args, **kwargs):
            if orig_init is not None:
                orig_init(self, *args, **kwargs)
            default_model = deepcopy(group._model_instance)
            object.__setattr__(self, root_name, default_model)

        setattr(plugin_class, "__init__", __init__)

        def simplify_schema(schema):
            """
            Simplify a JSON schema by consolidating identical definitions through multiple passes.
            """
            if not isinstance(schema, dict) or "$defs" not in schema:
                return schema

            # Working copy of definitions
            defs = deepcopy(schema["$defs"])
            # Final mapping of all old refs to new canonical refs
            total_ref_mappings = {}

            def get_signature(def_schema):
                """Helper to create a structural signature for a schema definition"""
                if not isinstance(def_schema, dict) or "properties" not in def_schema:
                    return str(def_schema)

                structure = {}
                for prop_name, prop_def in def_schema.get("properties", {}).items():
                    prop_structure = deepcopy(prop_def)
                    for key_to_remove in ["default", "title", "description"]:
                        if key_to_remove in prop_structure:
                            del prop_structure[key_to_remove]
                    structure[prop_name] = prop_structure

                # Sort by key for a consistent signature
                return str(sorted(structure.items()))

            def update_refs_recursive(obj, mappings):
                """Helper to apply reference mappings recursively"""
                if isinstance(obj, dict):
                    if "$ref" in obj and obj["$ref"] in mappings:
                        obj["$ref"] = mappings[obj["$ref"]]
                    for value in obj.values():
                        update_refs_recursive(value, mappings)
                elif isinstance(obj, list):
                    for item in obj:
                        update_refs_recursive(item, mappings)

            while True:
                # Group definitions by signature in the current state of `defs`
                schema_groups = {}
                for def_name, def_schema in defs.items():
                    signature = get_signature(def_schema)
                    if signature not in schema_groups:
                        schema_groups[signature] = []
                    schema_groups[signature].append(def_name)

                # Determine mappings for this pass
                pass_ref_mappings = {}
                for signature, def_names in schema_groups.items():
                    if len(def_names) > 1:
                        # Deterministic canonical choice (shortest name, then alphabetical)
                        canonical_name = sorted(def_names, key=lambda n: (len(n), n))[0]
                        for other_name in def_names:
                            if other_name != canonical_name:
                                pass_ref_mappings[f"#/$defs/{other_name}"] = (
                                    f"#/$defs/{canonical_name}"
                                )

                # If no new mappings were found, the structure has stabilized
                if not pass_ref_mappings:
                    break

                # Apply the new mappings to the definitions themselves to prepare for the next iteration
                update_refs_recursive(defs, pass_ref_mappings)

                # Update the total mapping, resolving chains.
                for old_ref, new_ref in pass_ref_mappings.items():
                    # For all existing mappings that point to `old_ref`, make them point to `new_ref`
                    for k, v in total_ref_mappings.items():
                        if v == old_ref:
                            total_ref_mappings[k] = new_ref
                    # Add the new mapping
                    total_ref_mappings[old_ref] = new_ref

                # Remove the consolidated (non-canonical) definitions from our working set
                for old_ref in pass_ref_mappings.keys():
                    def_name_to_remove = old_ref.split("/")[-1]
                    if def_name_to_remove in defs:
                        del defs[def_name_to_remove]

            # Create the final schema
            final_schema = deepcopy(schema)
            final_schema["$defs"] = defs

            # Apply the total mappings to the whole schema structure
            update_refs_recursive(final_schema, total_ref_mappings)

            return final_schema

        def settings_schema(self) -> dict[str, Any]:
            # Get raw schema and simplify it
            raw_schema = group._model_cls.model_json_schema()
            return simplify_schema(raw_schema)

        setattr(plugin_class, "settings_schema", settings_schema)

        def settings_dict(self) -> dict[str, Any]:
            return getattr(self, root_name).model_dump(mode="json")

        setattr(plugin_class, "settings_dict", settings_dict)

        return plugin_class

    return decorator
