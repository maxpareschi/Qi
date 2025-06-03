import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from pydantic_settings import SettingsError

# Import the parts of config.py we want to test
from core.config import CONFIG_FILE, DOTENV_FILE, QiConfigManager
from core.constants import BASE_PATH as CONST_BASE_PATH  # For comparison

# Mark tests as synchronous if no async operations


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Fixture to set and unset environment variables for testing."""
    original_env = os.environ.copy()
    yield monkeypatch  # Allows tests to set specific env vars
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_config_files():
    """Fixture to mock file system operations for config files."""
    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch("builtins.open", new_callable=mock_open) as mock_file_open,
    ):
        yield mock_exists, mock_file_open


# --- Test QiConfigManager Default Values and Basic Loading --- #


def test_qiconfigmanager_defaults(mock_env_vars, mock_config_files):
    mock_exists, _ = mock_config_files
    mock_exists.return_value = False  # No config files exist

    config = QiConfigManager()

    assert config.dev_mode is False
    assert config.log_level == "INFO"
    assert config.headless is False
    assert config.host == "localhost"
    assert config.port == 8000
    assert config.ssl_cert_path == ""
    assert config.ssl_key_path == ""
    assert (
        Path(config.base_path).resolve().as_posix()
        == Path(CONST_BASE_PATH).resolve().as_posix()
    )
    assert config.addon_paths == []  # Default empty string parses to empty list
    assert config.addon_dev_servers == {}
    assert config.reply_timeout == 5.0
    assert config.max_pending_requests_per_session == 100


# --- Test Environment Variable Overrides --- #


def test_qiconfigmanager_env_overrides(mock_env_vars, mock_config_files):
    mock_exists, _ = mock_config_files
    mock_exists.return_value = False  # No config files

    mock_env_vars.setenv("QI_DEV_MODE", "true")
    mock_env_vars.setenv("QI_LOG_LEVEL", "DEBUG")
    mock_env_vars.setenv("QI_HOST", "0.0.0.0")
    mock_env_vars.setenv("QI_PORT", "9090")
    mock_env_vars.setenv(
        "QI_ADDON_PATHS", "/path/one:/path/two"
    )  # Assuming POSIX style for test
    # For Windows, os.pathsep would be ';'
    # If testing on windows, adjust or use a helper to make platform agnostic
    if os.name == "nt":
        mock_env_vars.setenv("QI_ADDON_PATHS", "C:\\path\\one;C:\\path\\two")

    config = QiConfigManager()

    assert config.dev_mode is True
    assert (
        config.log_level == "DEBUG"
    )  # Dev mode also forces DEBUG, but test direct env var impact before model_validator
    assert config.host == "0.0.0.0"
    assert config.port == 9090
    if os.name == "nt":
        assert Path("C:/path/one").resolve().as_posix() in config.addon_paths
        assert Path("C:/path/two").resolve().as_posix() in config.addon_paths
    else:
        assert Path("/path/one").resolve().as_posix() in config.addon_paths
        assert Path("/path/two").resolve().as_posix() in config.addon_paths


# --- Test TOML File Loading --- #


def test_qiconfigmanager_toml_loading(mock_env_vars, mock_config_files):
    mock_exists, mock_file = mock_config_files

    # Simulate only qi.config.toml exists
    def exists_side_effect(path_arg):
        return str(path_arg) == CONFIG_FILE

    mock_exists.side_effect = exists_side_effect

    toml_content = """
[qi]
dev_mode = true
log_level = "WARNING"
host = "toml_host"
addon_paths = ["/toml/path1", "/toml/path2"]
    """
    mock_file.return_value.read.return_value = toml_content.encode("utf-8")

    config = QiConfigManager()

    assert config.dev_mode is True
    assert (
        config.log_level == "DEBUG"
    )  # dev_mode=True in TOML will force DEBUG via model_validator
    assert config.host == "toml_host"
    assert Path("/toml/path1").resolve().as_posix() in config.addon_paths
    assert Path("/toml/path2").resolve().as_posix() in config.addon_paths


# --- Test .env File Loading (dotenv_settings source) --- #


def test_qiconfigmanager_dotenv_loading(mock_env_vars, mock_config_files):
    mock_exists, mock_file = mock_config_files

    # Simulate only .env file exists
    def exists_side_effect(path_arg):
        return str(path_arg) == DOTENV_FILE

    mock_exists.side_effect = exists_side_effect

    dotenv_content = """
QI_HOST="dotenv_host"
QI_PORT=7070
QI_DEV_MODE=false
    """
    # mock_open needs to handle read for .env
    # Pydantic-settings will open this file, so mock_file should cater to it
    mock_file.return_value.read.return_value = dotenv_content

    config = QiConfigManager()

    assert config.host == "dotenv_host"
    assert config.port == 7070
    assert config.dev_mode is False
    assert config.log_level == "INFO"  # Default, since dev_mode is false


# --- Test Source Priority: Env > .env > TOML > Defaults --- #


def test_qiconfigmanager_source_priority(mock_env_vars, mock_config_files):
    mock_exists, mock_file = mock_config_files
    mock_exists.return_value = True  # Assume all config files exist

    # 1. TOML values
    toml_content = """
[qi]
host = "toml_host"
port = 1111
dev_mode = false # TOML says dev_mode is false
    """
    # 2. .env values (should override TOML)
    dotenv_content = """
QI_HOST="dotenv_host"
QI_PORT=2222
# QI_DEV_MODE not set in .env, so TOML's false will be used at this stage if env not set
    """
    # 3. Environment variables (should override .env and TOML)
    mock_env_vars.setenv("QI_HOST", "env_host")
    # QI_PORT not set in env, so .env's 2222 should be used
    # QI_DEV_MODE not set in env

    # Mock file reads for both
    def open_side_effect(path_arg, mode):
        if str(path_arg) == CONFIG_FILE:
            return mock_open(read_data=toml_content.encode("utf-8"))(path_arg, mode)
        elif str(path_arg) == DOTENV_FILE:
            return mock_open(read_data=dotenv_content)(path_arg, mode)
        return mock_open()(path_arg, mode)  # Default mock_open for other calls

    mock_file.side_effect = open_side_effect

    config = QiConfigManager()

    assert config.host == "env_host"  # Env overrides .env and TOML
    assert config.port == 2222  # .env overrides TOML (env not set)
    assert config.dev_mode is False  # From TOML, as not in .env or env vars
    assert config.log_level == "INFO"  # Based on dev_mode being False

    # Test with dev_mode from env var (highest priority)
    mock_env_vars.setenv("QI_DEV_MODE", "true")
    config_env_dev = QiConfigManager()
    assert config_env_dev.dev_mode is True
    assert (
        config_env_dev.log_level == "DEBUG"
    )  # Overrides previous log level due to dev_mode


# --- Test Field Validators and Model Validators --- #


def test_addon_paths_validator():
    raw_paths_str = f"/abs/path1{os.pathsep}./rel/path2{os.pathsep}path3"
    expected = [
        Path("/abs/path1").resolve().as_posix(),
        Path("./rel/path2").resolve().as_posix(),
        Path("path3").resolve().as_posix(),
    ]
    # Test with string input
    validated_str = QiConfigManager._parse_addon_paths(raw_paths_str)
    assert validated_str == expected

    # Test with list input
    raw_paths_list = ["/abs/path1", "./rel/path2", "path3"]
    validated_list = QiConfigManager._parse_addon_paths(raw_paths_list)
    assert validated_list == expected

    # Test with empty string
    assert QiConfigManager._parse_addon_paths("") == []
    # Test with list of empty/whitespace strings (should be filtered)
    assert QiConfigManager._parse_addon_paths(["", " "]) == []


def test_log_level_validator():
    assert QiConfigManager._normalize_log_level("info") == "INFO"
    assert QiConfigManager._normalize_log_level("DEBUG") == "DEBUG"


def test_base_path_validator():
    assert (
        QiConfigManager._normalize_base_path("/custom/path")
        == Path("/custom/path").resolve().as_posix()
    )
    # Default if empty string provided
    assert (
        QiConfigManager._normalize_base_path("")
        == Path(CONST_BASE_PATH).resolve().as_posix()
    )


def test_dev_mode_setup_model_validator(mock_env_vars, mock_config_files):
    mock_exists, _ = mock_config_files
    mock_exists.return_value = False

    # Scenario 1: dev_mode is True, log_level should become DEBUG
    mock_env_vars.setenv("QI_DEV_MODE", "true")
    mock_env_vars.setenv("QI_LOG_LEVEL", "INFO")  # Should be overridden
    config1 = QiConfigManager()
    assert config1.dev_mode is True
    assert config1.log_level == "DEBUG"
    mock_env_vars.clear()

    # Scenario 2: dev_mode is False, log_level should remain as specified
    mock_env_vars.setenv("QI_DEV_MODE", "false")
    mock_env_vars.setenv("QI_LOG_LEVEL", "WARNING")
    config2 = QiConfigManager()
    assert config2.dev_mode is False
    assert config2.log_level == "WARNING"


# --- Test Error Handling --- #


def test_invalid_toml_file_raises_settings_error(mock_env_vars, mock_config_files):
    mock_exists, mock_file = mock_config_files
    mock_exists.return_value = True  # qi.config.toml exists
    mock_file.return_value.read.return_value = b"this is not valid toml content: {"

    with pytest.raises(SettingsError) as exc_info:
        # This needs to be tested at the point where QiConfigManager is instantiated
        # in the module, or by directly calling a method that loads it if isolated.
        # For now, assume QiConfigManager() constructor will trigger the load.
        QiConfigManager()
    assert "Failed to load configuration file" in str(exc_info.value)


# --- Test QiConfigManager instance from module (qi_config) --- #
# These tests check the globally loaded qi_config instance if its module is re-imported or reloaded.
# This can be complex to test without specific mechanisms to force re-import with new mocks.
# The above tests focus on the QiConfigManager class itself.
# If core.config.py is imported, qi_config = QiConfigManager() runs immediately.
# To test the instance `qi_config` with mocks, the mocks need to be active *before* `core.config` is imported by the test module.


# Example of how one might attempt to test the module-level instance (can be tricky):
@patch.dict(os.environ, {"QI_HOST": "module_instance_test_host"}, clear=True)
@patch("pathlib.Path.exists", return_value=False)  # No config files
def test_module_qi_config_instance_loads_from_env(mock_exists_module_scope):
    # Need to force re-evaluation of core.config module or its QiConfigManager instantiation
    # This usually requires `importlib.reload`
    import importlib

    import core.config

    importlib.reload(core.config)
    assert core.config.qi_config.host == "module_instance_test_host"

    # Clean up by reloading again without the env var or restoring original state
    # This is important to avoid interference with other tests.
    del os.environ["QI_HOST"]
    importlib.reload(core.config)
