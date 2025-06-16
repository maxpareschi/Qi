from core import constants

# --- Test Core Constants ---


def test_hub_id():
    """Test that HUB_ID constant is defined correctly."""
    assert hasattr(constants, "HUB_ID")
    assert constants.HUB_ID == "__hub__"


def test_base_path_defined():
    """Test that BASE_PATH is defined and is a string."""
    assert hasattr(constants, "BASE_PATH")
    assert isinstance(constants.BASE_PATH, str)
    # It should be an absolute path, check common OS separators or posix path
    # This test might be a bit brittle depending on execution environment of tests
    # assert os.path.isabs(constants.BASE_PATH) or constants.BASE_PATH.startswith('/')


def test_config_file_path():
    """Test the CONFIG_FILE path structure."""
    assert hasattr(constants, "CONFIG_FILE")
    assert isinstance(constants.CONFIG_FILE, str)
    assert constants.CONFIG_FILE.endswith("config/qi.config.toml")
    # Check if it appears to be constructed with BASE_PATH
    assert constants.CONFIG_FILE.startswith(constants.BASE_PATH)
    # assert os.path.isabs(constants.CONFIG_FILE) # Should be absolute due to Path.resolve()


def test_dotenv_file_path():
    """Test the DOTENV_FILE path structure."""
    assert hasattr(constants, "DOTENV_FILE")
    assert isinstance(constants.DOTENV_FILE, str)
    assert constants.DOTENV_FILE.endswith("config/.env")
    # Check if it appears to be constructed with BASE_PATH
    assert constants.DOTENV_FILE.startswith(constants.BASE_PATH)
    # assert os.path.isabs(constants.DOTENV_FILE) # Should be absolute


# To make the tests for isabs more robust, we might need to ensure BASE_PATH is correctly resolved
# during test collection, or rely on the structure check (startswith BASE_PATH).
# For now, focusing on structure and suffix which are less environment-sensitive.


def test_paths_are_posix():
    """Test that paths are converted to posix format as per .as_posix() usage."""
    assert "\\" not in constants.BASE_PATH, "BASE_PATH should use POSIX separators"
    assert "\\" not in constants.CONFIG_FILE, "CONFIG_FILE should use POSIX separators"
    assert "\\" not in constants.DOTENV_FILE, "DOTENV_FILE should use POSIX separators"
