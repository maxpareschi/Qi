import logging
import re
from unittest.mock import patch

import pytest

from core.logger import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    QiCustomFormatter,
    get_logger,
    root_logger,  # Access to check its level
    set_level,
)
from core.logger import (
    handler as qi_global_handler,  # Access to check its level
)

# Mark all tests in this module as asyncio if any async functions are used
# These logging tests are synchronous.


@pytest.fixture(autouse=True)
def reset_logging_state():
    """Fixture to reset global logging state before and after each test."""
    original_root_level = root_logger.level
    original_handler_level = qi_global_handler.level
    # Potentially store and restore handlers if tests add/remove them
    yield
    root_logger.setLevel(original_root_level)
    qi_global_handler.setLevel(original_handler_level)
    # If formatters were changed, restore them too if necessary


# --- Test set_level --- #


def test_set_level_updates_root_and_handler():
    set_level(WARNING)
    assert root_logger.level == WARNING
    assert qi_global_handler.level == WARNING

    set_level(DEBUG)
    assert root_logger.level == DEBUG
    assert qi_global_handler.level == DEBUG


# --- Test get_logger --- #


def test_get_logger_returns_logger_instance():
    logger = get_logger("test_logger_instance")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger_instance"


def test_get_logger_sets_level_from_argument():
    _ = get_logger("test_arg_level", level=ERROR)
    assert root_logger.level == ERROR
    assert qi_global_handler.level == ERROR


@patch("core.logger.qi_launch_config")
def test_get_logger_dev_mode_true_sets_debug(mock_qi_launch_config):
    mock_qi_launch_config.dev_mode = True
    mock_qi_launch_config.log_level = "INFO"  # This should be overridden by dev_mode

    _ = get_logger("test_dev_mode_logger")
    assert root_logger.level == DEBUG
    assert qi_global_handler.level == DEBUG


@patch("core.logger.qi_launch_config")
def test_get_logger_dev_mode_false_uses_config_level(mock_qi_launch_config):
    mock_qi_launch_config.dev_mode = False
    mock_qi_launch_config.log_level = "WARNING"

    _ = get_logger("test_prod_mode_logger_warning")
    assert root_logger.level == WARNING
    assert qi_global_handler.level == WARNING

    mock_qi_launch_config.log_level = "CRITICAL"
    _ = get_logger("test_prod_mode_logger_critical")
    assert root_logger.level == CRITICAL
    assert qi_global_handler.level == CRITICAL


@patch("core.logger.qi_launch_config")
def test_get_logger_level_arg_overrides_config(mock_qi_launch_config):
    mock_qi_launch_config.dev_mode = True  # Should be overridden by level arg
    mock_qi_launch_config.log_level = "INFO"  # Should be overridden by level arg

    _ = get_logger("test_override_logger", level=ERROR)
    assert root_logger.level == ERROR
    assert qi_global_handler.level == ERROR


# --- Test QiCustomFormatter --- #


@pytest.fixture
def custom_formatter() -> QiCustomFormatter:
    return QiCustomFormatter()


@pytest.fixture
def sample_log_record() -> logging.LogRecord:
    # Create a basic LogRecord instance
    return logging.LogRecord(
        name="TestLogger.module",
        level=INFO,
        pathname="test_path/test_file.py",
        lineno=42,
        msg="This is a test message with some data: %s",
        args=("sample_arg",),
        exc_info=None,
        func="test_function_name",
    )


def test_qicustomformatter_formats_log_record(
    custom_formatter: QiCustomFormatter, sample_log_record: logging.LogRecord
):
    formatted_string = custom_formatter.format(sample_log_record)

    assert isinstance(formatted_string, str)

    # Check for key components (exact colors are hard to test reliably)
    assert (
        sample_log_record.getMessage() in formatted_string
    )  # "This is a test message with some data: sample_arg"
    assert "INFO" in formatted_string  # Log level name
    assert "TestLogger.module" in formatted_string  # Logger name
    assert "test_function_name" in formatted_string  # Function name
    assert "test_file.py:42" in formatted_string  # Filename and lineno

    # Check for timestamp placeholder format (actual time varies)
    # Example: 23-07-21 10:30:00 (based on %y-%m-%d %H:%M:%S)
    # This regex checks for DD-MM-YY HH:MM:SS format more or less
    assert re.match(r".*\d{2}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.*", formatted_string)


def test_qicustomformatter_level_colors_applied_in_format(
    custom_formatter: QiCustomFormatter,
):
    # Test that different levels result in different color codes being present (indirectly)
    # This is a bit of a proxy test since we can't easily check actual colors in terminal output.
    # We assume different levels use different LEVEL_COLORS/MESSAGE_COLORS which have distinct ANSI codes.

    debug_record = logging.LogRecord("test", DEBUG, "p", 1, "dbg", (), None, "f")
    info_record = logging.LogRecord("test", INFO, "p", 1, "inf", (), None, "f")
    warning_record = logging.LogRecord("test", WARNING, "p", 1, "wrn", (), None, "f")
    error_record = logging.LogRecord("test", ERROR, "p", 1, "err", (), None, "f")
    critical_record = logging.LogRecord("test", CRITICAL, "p", 1, "crit", (), None, "f")

    formatted_debug = custom_formatter.format(debug_record)
    formatted_info = custom_formatter.format(info_record)
    formatted_warning = custom_formatter.format(warning_record)
    formatted_error = custom_formatter.format(error_record)
    formatted_critical = custom_formatter.format(critical_record)

    # Check that they are different, implying different formatting due to colors
    # This isn't a perfect test for colors, but shows the formatter reacts to level.
    assert formatted_debug != formatted_info
    assert formatted_info != formatted_warning
    assert formatted_warning != formatted_error
    assert formatted_error != formatted_critical

    # Check for the reset code at the end of each formatted string
    reset_code = "\033[0m"
    assert formatted_debug.strip().endswith(
        reset_code.strip()
    )  # .strip() in case of trailing spaces from format
    assert formatted_info.strip().endswith(reset_code.strip())
    assert formatted_warning.strip().endswith(reset_code.strip())
    assert formatted_error.strip().endswith(reset_code.strip())
    assert formatted_critical.strip().endswith(reset_code.strip())


# Test for UTF-8 handling (if possible to set up a mock stream)
# This part might be too complex for unit testing without more infrastructure.
# For example, by temporarily redirecting sys.stdout to an io.BytesIO buffer
# and then checking the encoding of what's written.
# The current code tries to reconfigure handler.stream if available.
