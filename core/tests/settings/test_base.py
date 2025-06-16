import pytest

from core.settings.base import QiGroup, QiProp, QiSettings


def test_basic_assignment_and_serialization():
    root = QiSettings()
    with root as r:
        r.foo = QiProp(123)
        r.bar = QiProp(
            "hello", title="Bar Label", extra={"choices": ["hello", "world"]}
        )

    schema = root.get_model_schema()
    values = root.get_values()
    assert values["foo"] == 123
    # Note: Schema structure is different in Pydantic JSON schema
    assert "foo" in schema["properties"]
    assert values["bar"] == "hello"
    assert schema["properties"]["bar"]["title"] == "Bar Label"
    assert schema["properties"]["bar"]["extra"] == {"choices": ["hello", "world"]}


def test_nested_assignment_and_label_inference():
    root = QiSettings()
    with root as r:
        r.advanced = QiGroup()  # First create the group
        with r.advanced as adv:  # Then use it as context manager
            adv.threshold = QiProp(0.5)
            adv.mode = QiProp("auto")

    schema = root.get_model_schema()
    values = root.get_values()
    assert "advanced" in schema["properties"]
    assert values["advanced"]["threshold"] == 0.5
    # Nested schema structure - Pydantic uses $ref for nested models
    advanced_schema = schema["properties"]["advanced"]
    if "properties" in advanced_schema:
        assert "threshold" in advanced_schema["properties"]
    elif "$ref" in advanced_schema:
        # Check the referenced model in $defs
        ref_path = advanced_schema["$ref"]
        if ref_path.startswith("#/$defs/"):
            model_name = ref_path.split("/")[-1]
            if model_name in schema.get("$defs", {}):
                ref_schema = schema["$defs"][model_name]
                assert "threshold" in ref_schema.get("properties", {})
    assert values["advanced"]["mode"] == "auto"


def test_nested_group_assignment():
    root = QiSettings()
    with root as r:
        r.profile = QiGroup()
        with r.profile as profile:
            profile.level = QiProp(10)

    schema = root.get_model_schema()
    values = root.get_values()
    assert "profile" in schema["properties"]

    # Check the nested schema structure - Pydantic uses $ref for nested models
    profile_schema = schema["properties"]["profile"]
    assert values["profile"]["level"] == 10

    # Check if level exists in the referenced model
    if "properties" in profile_schema:
        assert "level" in profile_schema["properties"]
    elif "$ref" in profile_schema:
        # Check the referenced model in $defs
        ref_path = profile_schema["$ref"]
        if ref_path.startswith("#/$defs/"):
            model_name = ref_path.split("/")[-1]
            if model_name in schema.get("$defs", {}):
                ref_schema = schema["$defs"][model_name]
                assert "level" in ref_schema.get("properties", {})


def test_set_defaults_on_group():
    root = QiSettings()
    with root as r:
        r.alpha = QiProp(1)
        r.beta = QiProp(2)
        r.gamma = QiGroup()  # First create the group
        with r.gamma as gamma:
            gamma.delta = QiProp(3)

    # Set defaults for the entire group using set_defaults
    root.set_defaults({"alpha": 42, "gamma": {"delta": 99}})

    # Check the defaults were applied
    values = root.get_values()
    assert values["alpha"] == 42
    assert values["gamma"]["delta"] == 99
    assert values["beta"] == 2  # unchanged


def test_simple_value_assignment():
    """Test that simple values get automatically wrapped in QiProp"""
    root = QiSettings()
    with root as r:
        r.simple_value = "hello"
        r.number = 42
        r.flag = True

    values = root.get_values()
    assert values["simple_value"] == "hello"
    assert values["number"] == 42
    assert values["flag"] is True


def test_inheritance():
    """Test the inherit functionality"""
    root = QiSettings()
    with root as r:
        r.base_config = QiGroup()  # First create the group
        with r.base_config as base:
            base.name = QiProp("test")
            base.enabled = QiProp(True)

    # Test that inheritance creates a copy
    inherited = root.base_config.inherit()
    assert inherited is not root.base_config

    # Test that the inherited copy has the same structure
    assert len(inherited._children) == len(root.base_config._children)

    # Test that the original values are accessible
    values = root.get_values()
    assert "base_config" in values
    assert values["base_config"]["name"] == "test"
    assert values["base_config"]["enabled"] is True


def test_modifiable_collection_behavior():
    """Test modifiable=True creates collections (dict[str, Model])"""
    root = QiSettings()
    with root as r:
        r.profiles = QiGroup(modifiable=True, default_key="default")
        with r.profiles as profiles:
            profiles.name = QiProp("test")
            profiles.enabled = QiProp(True)

    values = root.get_values()
    schema = root.get_model_schema()

    # Should create a collection with the default key
    assert "profiles" in values
    assert "default" in values["profiles"]
    assert values["profiles"]["default"]["name"] == "test"
    assert values["profiles"]["default"]["enabled"] is True

    # Schema should show it's a dict type
    profiles_schema = schema["properties"]["profiles"]
    assert profiles_schema.get("type") == "object" or "$ref" in profiles_schema


def test_modifiable_list_behavior():
    """Test modifiable=True + list_mode=True creates lists"""
    root = QiSettings()
    with root as r:
        r.items = QiGroup(modifiable=True, list_mode=True)
        with r.items as items:
            items.name = QiProp("test")
            items.value = QiProp(42)

    values = root.get_values()
    schema = root.get_model_schema()

    # Should create an empty list (no defaults for list mode)
    assert "items" in values
    assert values["items"] == []

    # Schema should show it's an array type
    items_schema = schema["properties"]["items"]
    assert items_schema.get("type") == "array"


def test_error_conditions():
    """Test various error conditions"""
    # Test list_mode + default_key conflict
    with pytest.raises(ValueError, match="list_mode=True conflicts with default_key"):
        QiGroup(list_mode=True, default_key="test")

    # Test set_default_key on non-modifiable group
    root = QiSettings()
    with root as r:
        r.simple = QiGroup()  # modifiable=False by default

    with pytest.raises(
        RuntimeError, match="default_key applies only to modifiable groups"
    ):
        root.simple.set_default_key("test")


def test_error_on_unbuilt_access():
    """Test that accessing values before build raises appropriate errors"""
    root = QiGroup()  # Not QiSettings, so won't auto-build
    root.test = QiProp(42)

    with pytest.raises(RuntimeError, match="Settings not built yet"):
        root.get_values()

    with pytest.raises(RuntimeError, match="Settings not built yet"):
        root.get_model_schema()


# ====================================================================
# REAL-WORLD PLUGIN PATTERNS
# ====================================================================


def test_complex_plugin_pattern():
    """
    Real-world example: Plugin with nested collections and inheritance

    This pattern demonstrates:
    - Complex nested structures (profiles -> capabilities)
    - Modifiable collections with auto-captured defaults
    - Inheritance between collections
    - Merging additional entries via set_defaults()
    """
    # Create plugin settings structure
    settings = QiSettings(title="MyPlugin")
    with settings as s:
        s.enabled = True

        # Collection of user profiles with complex nested structure
        s.internal_profiles = QiGroup(default_key="adm_assistant", modifiable=True)
        with s.internal_profiles as p:
            p.name = "John"
            p.age = 24
            p.capabilities = QiGroup()  # Non-modifiable nested group

            with p.capabilities as c:
                c.attitudes = QiProp(
                    ["precise"], choices=["precise", "punctual", "leader", "efficient"]
                )
                c.skills = ["python"]

        # Inherit the structure for external profiles
        s.external_profiles = s.internal_profiles.inherit(defaults=True)

    # Verify initial state after context manager auto-capture
    values = settings.get_values()

    # Both collections should have the auto-captured "adm_assistant" entry
    assert "internal_profiles" in values
    assert "adm_assistant" in values["internal_profiles"]
    assert values["internal_profiles"]["adm_assistant"]["name"] == "John"
    assert values["internal_profiles"]["adm_assistant"]["age"] == 24
    assert values["internal_profiles"]["adm_assistant"]["capabilities"][
        "attitudes"
    ] == ["precise"]
    assert values["internal_profiles"]["adm_assistant"]["capabilities"]["skills"] == [
        "python"
    ]

    # External profiles should inherit the same structure
    assert "external_profiles" in values
    assert "adm_assistant" in values["external_profiles"]
    assert values["external_profiles"]["adm_assistant"]["name"] == "John"

    # Add additional entries via set_defaults (simulating config loading)
    settings.set_defaults(
        {
            "internal_profiles": {
                "adm_leader": {
                    "name": "Jill",
                    "age": 30,
                    "capabilities": {
                        "attitudes": ["efficient", "leader"],
                        "skills": ["python", "javascript", "excel"],
                    },
                },
                "adm_junior": {
                    "name": "Jane",
                    "age": 20,
                    "capabilities": {
                        "attitudes": ["precise", "punctual"],
                        "skills": ["python", "javascript"],
                    },
                },
            },
            "external_profiles": {
                "external_1": {
                    "name": "Jack",
                    "age": 25,
                    "capabilities": {
                        "attitudes": ["punctual"],
                        "skills": ["javascript", "excel"],
                    },
                }
            },
        }
    )

    # Verify merging behavior - original + new entries
    final_values = settings.get_values()

    # Internal profiles should have 3 entries: original + 2 new
    internal = final_values["internal_profiles"]
    assert len(internal) == 3
    assert "adm_assistant" in internal  # Original inherited
    assert "adm_leader" in internal  # New from set_defaults
    assert "adm_junior" in internal  # New from set_defaults

    # External profiles should have 2 entries: original + 1 new
    external = final_values["external_profiles"]
    assert len(external) == 2
    assert "adm_assistant" in external  # Original inherited
    assert "external_1" in external  # New from set_defaults

    # Verify complex nested structure is preserved
    leader = internal["adm_leader"]
    assert leader["name"] == "Jill"
    assert leader["capabilities"]["attitudes"] == ["efficient", "leader"]
    assert leader["capabilities"]["skills"] == ["python", "javascript", "excel"]


def test_inheritance_with_and_without_defaults():
    """
    Test inherit(defaults=True/False) behavior with collections

    This demonstrates:
    - defaults=True preserves auto-captured collection entries
    - defaults=False creates empty collections (schema only)
    """
    root = QiSettings()
    with root as r:
        # Create a collection with captured defaults
        r.source = QiGroup(modifiable=True, default_key="template")
        with r.source as src:
            src.name = "Default User"
            src.level = 1
            src.permissions = QiGroup()
            with src.permissions as perms:
                perms.read = True
                perms.write = False

        # Test inheritance with defaults
        r.copy_with_defaults = r.source.inherit(defaults=True)

        # Test inheritance without defaults (schema only)
        r.copy_without_defaults = r.source.inherit(defaults=False)

    values = root.get_values()

    # Source should have the template entry
    assert "template" in values["source"]
    assert values["source"]["template"]["name"] == "Default User"

    # copy_with_defaults should inherit the template entry
    assert "template" in values["copy_with_defaults"]
    assert values["copy_with_defaults"]["template"]["name"] == "Default User"
    assert values["copy_with_defaults"]["template"]["permissions"]["read"] is True

    # copy_without_defaults should be empty (schema only, no defaults)
    assert len(values["copy_without_defaults"]) == 0

    # But the schema structure should be identical for all three
    schema = root.get_model_schema()
    source_schema = schema["properties"]["source"]
    copy_with_schema = schema["properties"]["copy_with_defaults"]
    copy_without_schema = schema["properties"]["copy_without_defaults"]

    # All should be object types with additionalProperties
    assert source_schema.get("type") == "object" or "$ref" in source_schema
    assert copy_with_schema.get("type") == "object" or "$ref" in copy_with_schema
    assert copy_without_schema.get("type") == "object" or "$ref" in copy_without_schema


def test_three_modes_comprehensive():
    """
    Test all three QiGroup modes in one comprehensive example

    Demonstrates:
    1. Direct object (modifiable=False): Single nested object
    2. Collection (modifiable=True, list_mode=False): dict[str, Model]
    3. List (modifiable=True, list_mode=True): list[Model]
    """
    root = QiSettings()
    with root as r:
        # Mode 1: Direct object (single nested model)
        r.config = QiGroup()  # modifiable=False by default
        with r.config as cfg:
            cfg.host = "localhost"
            cfg.port = 8080
            cfg.ssl = False

        # Mode 2: Collection (dict of models)
        r.databases = QiGroup(modifiable=True, default_key="primary")
        with r.databases as dbs:
            dbs.host = "db.example.com"
            dbs.port = 5432
            dbs.name = "myapp"

        # Mode 3: List (list of models)
        r.servers = QiGroup(modifiable=True, list_mode=True)
        with r.servers as srv:
            srv.name = "server-template"
            srv.cpu_cores = 4
            srv.memory_gb = 16

    values = root.get_values()
    schema = root.get_model_schema()

    # Mode 1: Direct object - single nested object
    assert "config" in values
    assert values["config"]["host"] == "localhost"
    assert values["config"]["port"] == 8080
    config_schema = schema["properties"]["config"]
    # Should reference a single model (not additionalProperties or array)
    assert "$ref" in config_schema or "properties" in config_schema

    # Mode 2: Collection - dict with default entry
    assert "databases" in values
    assert "primary" in values["databases"]  # Auto-captured default
    assert values["databases"]["primary"]["host"] == "db.example.com"
    assert values["databases"]["primary"]["port"] == 5432
    db_schema = schema["properties"]["databases"]
    assert db_schema.get("type") == "object"
    assert "additionalProperties" in db_schema  # Indicates dict[str, Model]

    # Mode 3: List - empty list (no auto-capture for lists)
    assert "servers" in values
    assert values["servers"] == []  # List mode doesn't auto-capture
    server_schema = schema["properties"]["servers"]
    assert server_schema.get("type") == "array"
    assert "items" in server_schema  # Indicates list[Model]


def test_deep_nesting_and_merging():
    """
    Test complex nested structures and merging behavior

    This tests edge cases with:
    - Multiple levels of nesting
    - Mixed modifiable/non-modifiable groups
    - Complex merging via set_defaults()
    """
    root = QiSettings()
    with root as r:
        r.app = QiGroup(modifiable=True, default_key="main")
        with r.app as app:
            app.name = "MyApp"
            app.version = "1.0.0"

            # Nested non-modifiable group
            app.features = QiGroup()
            with app.features as features:
                features.auth = True
                features.logging = True

                # Deeply nested modifiable collection
                features.plugins = QiGroup(modifiable=True, default_key="core")
                with features.plugins as plugins:
                    plugins.name = "core-plugin"
                    plugins.enabled = True
                    plugins.config = QiGroup()
                    with plugins.config as cfg:
                        cfg.timeout = 30
                        cfg.retries = 3

    # Verify initial deep structure
    values = root.get_values()
    main_app = values["app"]["main"]
    assert main_app["name"] == "MyApp"
    assert main_app["features"]["auth"] is True
    assert "core" in main_app["features"]["plugins"]
    core_plugin = main_app["features"]["plugins"]["core"]
    assert core_plugin["name"] == "core-plugin"
    assert core_plugin["config"]["timeout"] == 30

    # Test complex merging with nested structures
    root.set_defaults(
        {
            "app": {
                "production": {
                    "name": "MyApp-Prod",
                    "version": "2.0.0",
                    "features": {
                        "auth": True,
                        "logging": False,  # Override
                        "plugins": {
                            "analytics": {
                                "name": "analytics-plugin",
                                "enabled": True,
                                "config": {"timeout": 60, "retries": 5},
                            }
                        },
                    },
                }
            }
        }
    )

    # Verify complex merging worked
    final_values = root.get_values()
    assert len(final_values["app"]) == 2  # main + production

    prod_app = final_values["app"]["production"]
    assert prod_app["name"] == "MyApp-Prod"
    assert prod_app["features"]["logging"] is False  # Overridden
    assert "analytics" in prod_app["features"]["plugins"]
    analytics = prod_app["features"]["plugins"]["analytics"]
    assert analytics["config"]["timeout"] == 60


def test_edge_cases_and_error_conditions():
    """
    Test various edge cases and error conditions
    """
    # Test default_key validation
    with pytest.raises(ValueError, match="default_key requires modifiable=True"):
        QiGroup(default_key="test", modifiable=False)

    # Test multiple inheritance chains
    root = QiSettings()
    with root as r:
        r.a = QiGroup(modifiable=True, default_key="original")
        with r.a as a:
            a.value = "first"

        r.b = r.a.inherit(defaults=True)
        r.c = r.b.inherit(defaults=True)  # Multiple inheritance levels

    values = root.get_values()
    # All should have the same inherited structure
    assert values["a"]["original"]["value"] == "first"
    assert values["b"]["original"]["value"] == "first"
    assert values["c"]["original"]["value"] == "first"

    # Test empty collections handle merging correctly
    empty_root = QiSettings()
    with empty_root as r:
        r.empty_collection = QiGroup(modifiable=True)  # No context manager body

    # Empty collections start as empty dicts
    empty_values = empty_root.get_values()
    assert "empty_collection" in empty_values
    assert empty_values["empty_collection"] == {}

    # Test that collections with schema can handle set_defaults
    schema_root = QiSettings()
    with schema_root as r:
        r.collection_with_schema = QiGroup(modifiable=True, default_key="template")
        with r.collection_with_schema as cws:
            cws.field = "default_value"

    # Should handle set_defaults on collection with defined schema
    schema_root.set_defaults(
        {"collection_with_schema": {"new_entry": {"field": "custom_value"}}}
    )

    schema_values = schema_root.get_values()
    assert "new_entry" in schema_values["collection_with_schema"]
    assert (
        schema_values["collection_with_schema"]["new_entry"]["field"] == "custom_value"
    )
    assert (
        "template" in schema_values["collection_with_schema"]
    )  # Original should still exist

    # Test accessing schema objects after build (for methods like inherit)
    root = QiSettings()
    with root as r:
        r.test_group = QiGroup(modifiable=True)

    # After build, should still be able to access original objects
    original_group = root.test_group
    inherited = original_group.inherit(defaults=False)
    assert inherited is not original_group
    assert inherited.modifiable is True
