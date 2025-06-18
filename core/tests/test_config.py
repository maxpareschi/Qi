import importlib
import os
import tomllib
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from pydantic_settings import SettingsError

from core.constants import BASE_PATH as CONST_BASE_PATH  # For comparison

# Import the parts of config.py we want to test
from core.launch_config import CONFIG_FILE, DOTENV_FILE, QiLaunchConfig

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


# --- Test QiLaunchConfig Default Values and Basic Loading --- #


def test_qiconfigmanager_defaults(mock_env_vars, mock_config_files):
    mock_exists, _ = mock_config_files
    mock_exists.return_value = False  # No config files exist

    config = QiLaunchConfig()

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

    config = QiLaunchConfig()

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
    # Patch Path.exists to always return True
    mock_exists.side_effect = lambda *args, **kwargs: True
    # TOML content must be valid and flush left
    toml_content = '[qi]\ndev_mode = true\nlog_level = "WARNING"\nhost = "toml_host"\naddon_paths = ["/toml/path1", "/toml/path2"]\n'

    def open_side_effect(path_arg, mode="r", *a, **k):
        if str(path_arg) == str(CONFIG_FILE):
            if "b" in mode:
                return mock_open(read_data=toml_content.encode("utf-8"))()
            else:
                return mock_open(read_data=toml_content)()
        return mock_open()()

    mock_file.side_effect = open_side_effect
    # Patch tomllib.load to return the expected dict and print when called
    with patch(
        "tomllib.load",
        side_effect=lambda f: print("DEBUG: tomllib.load called")
        or {
            "qi": {
                "dev_mode": True,
                "log_level": "WARNING",
                "host": "toml_host",
                "addon_paths": ["/toml/path1", "/toml/path2"],
            }
        },
    ):
        config = QiLaunchConfig()
    assert config.dev_mode is True
    assert config.log_level == "DEBUG", (
        f"Expected log_level DEBUG, got {config.log_level}"
    )
    assert config.host == "toml_host", f"Expected host 'toml_host', got {config.host}"
    expected_addon_paths = [
        Path("/toml/path1").resolve().as_posix(),
        Path("/toml/path2").resolve().as_posix(),
    ]
    assert sorted(config.addon_paths) == sorted(expected_addon_paths)


# --- Test .env File Loading (dotenv_settings source) --- #


def test_qiconfigmanager_dotenv_loading(mock_env_vars, mock_config_files):
    mock_exists, mock_file = mock_config_files

    print(f"DOTENV_FILE path for dotenv test: {DOTENV_FILE}")  # Debug print

    def debug_exists_side_effect_dotenv(*args, **kwargs):
        print(f"dotenv exists_side_effect called with: args={args}, kwargs={kwargs}")
        if args:
            path_instance = args[0]
            print(
                f"dotenv Path instance received: {path_instance}, type: {type(path_instance)}"
            )
            return str(path_instance) == DOTENV_FILE
        return False

    mock_exists.side_effect = debug_exists_side_effect_dotenv

    dotenv_content = """
QI_HOST="dotenv_host"
QI_PORT=7070
QI_DEV_MODE=false
    """
    # mock_open needs to handle read for .env
    # Pydantic-settings will open this file, so mock_file should cater to it
    mock_file.return_value.read.return_value = dotenv_content

    config = QiLaunchConfig()

    assert config.host == "dotenv_host"
    assert config.port == 7070
    assert config.dev_mode is False
    assert config.log_level == "INFO"  # Default, since dev_mode is false


# --- Test Source Priority: Env > .env > TOML > Defaults --- #


@patch("tomllib.load")
def test_qiconfigmanager_source_priority(mock_toml_load, mock_env_vars):
    """
    Tests the source priority: Env variables > .env files > TOML files.
    This test uses high-level patching to avoid complex file I/O mocking.
    """
    # 1. TOML values (lowest priority)
    mock_toml_load.return_value = {
        "qi": {
            "host": "toml_host",
            "port": 1111,
            "dev_mode": False,
        }
    }

    # 2. .env values (middle priority)
    # We patch the DotEnvSettingsSource to inject values directly
    with patch(
        "pydantic_settings.sources.DotEnvSettingsSource.__call__",
        return_value={"host": "dotenv_host", "port": "2222"},
    ) as mock_dotenv_source:
        # 3. Environment variables (highest priority)
        mock_env_vars.setenv("QI_HOST", "env_host")

        # --- Run test ---
        # We need to mock Path.exists for the TOML file to trigger tomllib.load
        with patch("pathlib.Path.exists", return_value=True):
            config = QiLaunchConfig()

        # --- Assertions ---
        # Assert that the correct sources were called
        mock_toml_load.assert_called_once()
        mock_dotenv_source.assert_called_once()

        # Assert values based on priority
        assert config.host == "env_host"  # Env var wins over all
        assert config.port == 2222  # .env wins over TOML
        assert config.dev_mode is False  # From TOML, as not in .env or env vars
        assert config.log_level == "INFO"  # Based on dev_mode being False

        # --- Test with dev_mode from env var ---
        mock_env_vars.setenv("QI_DEV_MODE", "true")
        with patch("pathlib.Path.exists", return_value=True):
            config_env_dev = QiLaunchConfig()

        # Env var for dev_mode should win as it was not in .env
        assert config_env_dev.dev_mode is True
        assert config_env_dev.log_level == "DEBUG"


# --- Test Field Validators and Model Validators --- #


@patch("core.launch_config.tomllib.load", return_value={})
def test_path_normalization_validators(mock_load, mock_env_vars, mock_config_files):
    """Tests that path-like fields are correctly normalized to absolute paths."""
    mock_exists, _ = mock_config_files
    mock_exists.return_value = False  # Isolate from local config files

    with patch("core.launch_config.tomllib.load", return_value={}):
        # Test custom paths
        config_custom = QiLaunchConfig(
            base_path="/custom/path", bundles_file="/custom/bundles.toml"
        )
        assert config_custom.base_path == Path("/custom/path").resolve().as_posix()
        assert (
            config_custom.bundles_file
            == Path("/custom/bundles.toml").resolve().as_posix()
        )

        # Test default paths (when input is empty or None)
        config_default = QiLaunchConfig(base_path="", bundles_file=None)
        assert config_default.base_path == Path(CONST_BASE_PATH).resolve().as_posix()
        # Assuming BUNDLES_FILE is imported or accessible
        from core.constants import BUNDLES_FILE

        assert config_default.bundles_file == Path(BUNDLES_FILE).resolve().as_posix()


def test_addon_paths_validator(mock_env_vars, mock_config_files):
    """Tests that addon_paths are parsed and normalized correctly."""
    mock_exists, _ = mock_config_files
    mock_exists.return_value = False  # Isolate from local config files

    with patch("core.launch_config.tomllib.load", return_value={}):
        # Test with a string of paths
        raw_paths_str = f"/abs/path1{os.pathsep}./rel/path2{os.pathsep}path3"
        config_str = QiLaunchConfig(addon_paths=raw_paths_str)
        expected = [
            Path("/abs/path1").resolve().as_posix(),
            Path("./rel/path2").resolve().as_posix(),
            Path("path3").resolve().as_posix(),
        ]
        assert sorted(config_str.addon_paths) == sorted(expected)

        # Test with a list of paths
        raw_paths_list = ["/abs/path1", "./rel/path2", "path3"]
        config_list = QiLaunchConfig(addon_paths=raw_paths_list)
        assert sorted(config_list.addon_paths) == sorted(expected)

        # Test with an empty string
        config_empty_str = QiLaunchConfig(addon_paths="")
        assert config_empty_str.addon_paths == []

        # Test with an empty list
        config_empty_list = QiLaunchConfig(addon_paths=[])
        assert config_empty_list.addon_paths == []


def test_log_level_validator(mock_env_vars, mock_config_files):
    """Tests that the log level is correctly uppercased."""
    mock_exists, _ = mock_config_files
    mock_exists.return_value = False  # Isolate from local config files

    with patch("core.launch_config.tomllib.load", return_value={}):
        config = QiLaunchConfig(log_level="debug")
        assert config.log_level == "DEBUG"


def test_dev_mode_setup_model_validator(mock_env_vars, mock_config_files):
    """
    Tests the model validator that sets log_level to DEBUG when dev_mode is True.
    """
    mock_exists, _ = mock_config_files
    mock_exists.return_value = False

    with patch("core.launch_config.tomllib.load", return_value={}):
        # 1. dev_mode=True should force log_level to DEBUG
        config_dev = QiLaunchConfig(dev_mode=True, log_level="INFO")
        assert config_dev.log_level == "DEBUG"

        # 2. dev_mode=False should respect the given log_level
        config_nodev = QiLaunchConfig(dev_mode=False, log_level="WARNING")
        assert config_nodev.log_level == "WARNING"

    # 3. Test with environment variable - this one is tricky as env overrides constructor
    mock_env_vars.setenv("QI_DEV_MODE", "true")
    with patch("core.launch_config.tomllib.load", return_value={}):
        config_env = QiLaunchConfig()  # No log_level in constructor
        assert config_env.log_level == "DEBUG"


# --- Test Error Handling --- #


def test_invalid_toml_file_raises_settings_error(mock_env_vars, mock_config_files):
    mock_exists, mock_file = mock_config_files
    mock_exists.return_value = True
    toml_content = "[qi]\ndev_mode = tru"  # Malformed boolean

    def open_side_effect(path_arg, mode="r", *a, **k):
        if str(path_arg) == str(CONFIG_FILE):
            if "b" in mode:  # Check if opened in binary mode
                return mock_open(read_data=toml_content.encode("utf-8"))()
            return mock_open(read_data=toml_content)()
        return mock_open()()

    mock_file.side_effect = open_side_effect

    with (
        patch("tomllib.load", side_effect=tomllib.TOMLDecodeError("Test Error")),
        pytest.raises(SettingsError, match="Error parsing TOML file"),
    ):
        QiLaunchConfig()


# This test is problematic because the module-level singleton `qi_launch_config`
# is instantiated upon module import. Re-testing its creation is difficult
# without complex test setups like `importlib.reload`.
# It's better to test the class `QiLaunchConfig` directly, as done in other tests.
@pytest.mark.xfail(
    reason="Module-level singleton cannot be reliably re-tested after import."
)
def test_module_qi_launch_config_instance_loads_from_env(mock_exists_module_scope):
    # This test would require reloading the core.launch_config module to be effective.
    # The current test structure with function-scoped fixtures doesn't support this well.
    import core.launch_config

    with patch.dict(os.environ, {"QI_HOST": "module_test_host"}):
        importlib.reload(core.launch_config)
        assert core.launch_config.qi_launch_config.host == "module_test_host"
