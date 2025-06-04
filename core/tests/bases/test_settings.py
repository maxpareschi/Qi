import pytest

from core.bases.settings import QiSetting, QiSettingsNode


def test_basic_assignment_and_serialization():
    root = QiSettingsNode()
    root.foo = QiSetting(123)
    root.bar = QiSetting(
        "hello", label="Bar Label", extra={"choices": ["hello", "world"]}
    )

    schema = root.get_schema()
    values = root.get_values()
    assert values["foo"] == 123
    assert schema["foo"]["label"] == "Foo"
    assert values["bar"] == "hello"
    assert schema["bar"]["label"] == "Bar Label"
    assert schema["bar"]["extra"] == {"choices": ["hello", "world"]}


def test_nested_assignment_and_label_inference():
    root = QiSettingsNode()
    with root.advanced as adv:
        adv.threshold = QiSetting(0.5)
        adv.mode = QiSetting("auto")

    schema = root.get_schema()
    values = root.get_values()
    assert "advanced" in schema
    assert values["advanced"]["threshold"] == 0.5
    assert schema["advanced"]["threshold"]["label"] == "Threshold"
    assert values["advanced"]["mode"] == "auto"


def test_context_manager_on_qisetting():
    root = QiSettingsNode()
    root.profile = QiSetting("user")
    with root.profile as node:
        node.level = QiSetting(10)
    schema = root.get_schema()
    values = root.get_values()
    assert "schema" in schema["profile"]
    assert "level" in schema["profile"]["schema"]
    assert schema["profile"]["schema"]["level"]["label"] == "Level"
    assert values["profile"]["level"] == 10


def test_set_defaults_on_leaf_and_node():
    root = QiSettingsNode()
    root.alpha = QiSetting(1)
    root.beta = QiSetting(2)
    with root.gamma as gamma:
        gamma.delta = QiSetting(3)

    # Set defaults for a leaf
    root.alpha.set_defaults(42)
    # Set defaults for a node (not supported in new API, so only test leaf)

    # Check the defaults tree
    values = root.get_values()
    assert values["alpha"] == 42
    # gamma.delta should still be 3 (default), as set_defaults on node is not supported
    assert values["gamma"]["delta"] == 3


def test_error_on_unattached_qisetting():
    s = QiSetting(1)
    with pytest.raises(RuntimeError):
        s.set_defaults(2)
    with pytest.raises(RuntimeError):
        s.__getattr__("foo")
    with pytest.raises(RuntimeError):
        s.__setattr__("foo", 3)
    with pytest.raises(RuntimeError):
        s.__enter__()
