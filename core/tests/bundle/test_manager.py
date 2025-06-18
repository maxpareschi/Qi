# core/tests/bundle/test_manager.py

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.bundle.manager import QiBundleManager

# Define a default fallback order for tests
TEST_FALLBACK_ORDER = ["prod", "dev"]

# Mark all tests in this module as asyncio, though they are synchronous
# pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def reset_bundle_manager_singleton():
    """
    Fixture to automatically reset the QiBundleManager singleton before each test.
    This prevents state from leaking between tests.
    """
    if hasattr(QiBundleManager, "_instance"):
        QiBundleManager._instance = None


@pytest.fixture
def mock_bundles_file(tmp_path: Path) -> Path:
    """Creates a mock bundles.toml file in a temporary directory."""
    bundles_content = """
[bundles.dev]
name = "dev"
allow_list = []
env = { QI_ENV = "development" }

[bundles.prod]
name = "prod"
allow_list = ["core", "maya"]
env = { QI_ENV = "production" }
"""
    file_path = tmp_path / "bundles.toml"
    file_path.write_text(bundles_content)
    return file_path


@pytest.fixture
def malformed_bundles_file(tmp_path: Path) -> Path:
    """Creates a malformed mock bundles.toml file."""
    bundles_content = """
[bundles.dev]
  name = "dev"
  allow_list = []
  env = { QI_ENV = "development"
# Missing closing brace
"""
    file_path = tmp_path / "bundles.toml"
    file_path.write_text(bundles_content)
    return file_path


def mock_qi_launch_config(mocker, bundles_file, default_name=None, fallback_order=None):
    """Helper to create a mock qi_launch_config object."""
    mock_config = MagicMock()
    mock_config.bundles_file = str(bundles_file)
    mock_config.default_bundle_name = default_name or "default_test_bundle"
    mock_config.bundle_fallback_order = fallback_order or []
    mocker.patch("core.bundle.manager.qi_launch_config", mock_config)
    return mock_config


def test_init_loads_bundles_from_valid_file(mock_bundles_file, mocker):
    """Tests that the manager correctly loads bundles from a valid TOML file."""
    mock_qi_launch_config(mocker, mock_bundles_file, fallback_order=TEST_FALLBACK_ORDER)
    manager = QiBundleManager()
    assert "dev" in manager.list_bundles()
    assert "prod" in manager.list_bundles()
    assert len(manager.list_bundles()) == 2


def test_init_falls_back_if_file_not_found(tmp_path, mocker):
    """Tests that the manager creates a default bundle if the file is missing."""
    non_existent_file = tmp_path / "non_existent.toml"
    mock_qi_launch_config(mocker, non_existent_file, default_name="test_default")
    manager = QiBundleManager()
    assert manager.list_bundles() == ["test_default"]
    active_bundle = manager.get_active_bundle()
    assert active_bundle.name == "test_default"
    assert active_bundle.allow_list == []


def test_init_falls_back_if_file_is_malformed(malformed_bundles_file, mocker):
    """Tests that the manager falls back to a default bundle if the file is corrupt."""
    mock_qi_launch_config(
        mocker, malformed_bundles_file, default_name="fallback_default"
    )
    manager = QiBundleManager()
    assert manager.list_bundles() == ["fallback_default"]
    assert manager.get_active_bundle().name == "fallback_default"


def test_list_bundles(mock_bundles_file, mocker):
    """Tests the list_bundles method."""
    mock_qi_launch_config(mocker, mock_bundles_file)
    manager = QiBundleManager()
    bundles = manager.list_bundles()
    assert isinstance(bundles, list)
    assert sorted(bundles) == ["dev", "prod"]


def test_get_active_bundle_default(mock_bundles_file, mocker):
    """Tests that the default active bundle is 'prod' based on fallback order."""
    mock_qi_launch_config(mocker, mock_bundles_file, fallback_order=TEST_FALLBACK_ORDER)
    manager = QiBundleManager()
    active_bundle = manager.get_active_bundle()
    assert active_bundle.name == "prod"


def test_set_active_bundle(mock_bundles_file, mocker):
    """Tests setting a new active bundle."""
    mock_qi_launch_config(mocker, mock_bundles_file, fallback_order=TEST_FALLBACK_ORDER)
    manager = QiBundleManager()
    # Initial active bundle is 'prod' from fallback order
    assert manager.set_active_bundle("dev") is True
    active_bundle = manager.get_active_bundle()
    assert active_bundle.name == "dev"
    assert active_bundle.allow_list == []


def test_set_active_bundle_not_found(mock_bundles_file, mocker):
    """Tests that setting a non-existent bundle fails and does not change the active bundle."""
    mock_qi_launch_config(mocker, mock_bundles_file, fallback_order=TEST_FALLBACK_ORDER)
    manager = QiBundleManager()
    initial_active = manager.get_active_bundle().name
    assert manager.set_active_bundle("non_existent") is False
    assert manager.get_active_bundle().name == initial_active


def test_env_for_bundle(mock_bundles_file, mocker):
    """Tests retrieving the environment for a specific bundle."""
    mock_qi_launch_config(mocker, mock_bundles_file, fallback_order=TEST_FALLBACK_ORDER)
    manager = QiBundleManager()

    # Test with specific bundle name
    prod_env = manager.env_for_bundle("prod")
    assert prod_env == {"QI_ENV": "production"}

    # Test with no name (should return env for active bundle)
    manager.set_active_bundle("dev")
    active_env = manager.env_for_bundle()
    assert active_env == {"QI_ENV": "development"}


def test_env_for_bundle_not_found(mock_bundles_file, mocker):
    """Tests retrieving the environment for a non-existent bundle returns an empty dict."""
    mock_qi_launch_config(mocker, mock_bundles_file)
    manager = QiBundleManager()
    env = manager.env_for_bundle("non_existent")
    assert env == {}


def test_bundle_name_mismatch_warning(tmp_path, mocker):
    """Tests that a bundle with mismatched key and name property is skipped."""
    bundles_content = """
[bundles.dev]
name = "developer"  # Mismatch: key is 'dev', name is 'developer'
allow_list = []
env = {}

[bundles.prod]
name = "prod"  # This one is correct
allow_list = []
env = {}
"""
    file_path = tmp_path / "bundles.toml"
    file_path.write_text(bundles_content)

    mock_qi_launch_config(mocker, file_path, fallback_order=["dev", "prod"])

    from unittest.mock import patch

    with patch("core.bundle.manager.log") as mock_log:
        manager = QiBundleManager()

        # Should log an error about the mismatch
        mock_log.error.assert_called()
        assert "Bundle name mismatch" in mock_log.error.call_args[0][0]

        # The mismatched bundle should be skipped
        assert "dev" not in manager.list_bundles()
        assert "prod" in manager.list_bundles()

        # Active bundle should be "prod" since "dev" was skipped
        assert manager.get_active_bundle().name == "prod"


def test_no_valid_bundles_raises_error(tmp_path, mocker):
    """Tests that an error is raised when no valid bundles are available after processing."""
    # Create a bundles file with only invalid bundles (name mismatches)
    bundles_content = """
[bundles.dev]
name = "developer"  # Mismatch: key is 'dev', name is 'developer'
allow_list = []
env = {}

[bundles.prod]
name = "production"  # Mismatch: key is 'prod', name is 'production'
allow_list = []
env = {}
"""
    file_path = tmp_path / "bundles.toml"
    file_path.write_text(bundles_content)

    mock_qi_launch_config(mocker, file_path, fallback_order=["dev", "prod"])

    # Should raise RuntimeError because no valid bundles are available
    with pytest.raises(
        RuntimeError, match="No bundles available after loading process"
    ):
        QiBundleManager()
