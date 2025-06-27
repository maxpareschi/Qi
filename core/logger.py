# core/logger.py

"""
Logger module.

This module provides a logging utility for the Qi system with custom formatting,
color support, and environment-based configuration. It's designed as a module-level
utility rather than a service for early availability and simplicity.
"""

import logging
import os
import sys

# ANSI color codes
COLORS = {
    "reset": "\033[0m",
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "purple": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "light_black": "\033[90m",
    "light_red": "\033[91m",
    "light_green": "\033[92m",
    "light_yellow": "\033[93m",
    "light_blue": "\033[94m",
    "light_purple": "\033[95m",
    "light_cyan": "\033[96m",
    "light_white": "\033[97m",
    "bold": "\033[1m",
    "bold_red": "\033[1;31m",
    "bold_white": "\033[1;37m",
    "bg_bold_red": "\033[1;41m",
    "fg_bold_white_bg_bold_red": "\033[1;37;41m",
}

LEVEL_COLORS = {
    "DEBUG": COLORS["cyan"],
    "INFO": COLORS["green"],
    "WARNING": COLORS["yellow"],
    "ERROR": COLORS["red"],
    "CRITICAL": COLORS["fg_bold_white_bg_bold_red"],
}

MESSAGE_COLORS = {
    "DEBUG": COLORS["light_black"],
    "INFO": COLORS["light_white"],
    "WARNING": COLORS["yellow"],
    "ERROR": COLORS["bold_red"],
    "CRITICAL": COLORS["fg_bold_white_bg_bold_red"],
}

# Logging level constants for convenience
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL


class QiCustomFormatter(logging.Formatter):
    """Custom formatter with color support and consistent layout."""

    def __init__(self, use_colors: bool = True):
        """
        Initialize formatter.

        Args:
            use_colors: Whether to use ANSI color codes (disable for file output)
        """
        super().__init__()
        self.use_colors = use_colors and self._supports_color()

    def _supports_color(self) -> bool:
        """Check if the terminal supports color output."""
        # Check if running in a terminal that supports colors
        if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
            return False

        # Windows terminal support
        if os.name == "nt":
            try:
                import colorama

                colorama.init()
                return True
            except ImportError:
                # Check for Windows 10+ with ANSI support
                return os.environ.get("TERM") or "ANSICON" in os.environ

        return True

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors and consistent layout."""
        # Format the timestamp
        record.asctime = self.formatTime(record, "%y-%m-%d %H:%M:%S")

        if self.use_colors:
            # Get colors for current log level
            log_color = LEVEL_COLORS.get(record.levelname, COLORS["reset"])
            message_color = MESSAGE_COLORS.get(record.levelname, COLORS["reset"])

            # Apply color formatting
            formatted = (
                f"{COLORS['light_black']}{record.asctime}{COLORS['reset']} | "
                f"{log_color}{record.levelname:<8}{COLORS['reset']} | "
                f"{message_color}{record.name:<20} | "
                f"{record.getMessage()}{COLORS['reset']} "
                f"{COLORS['light_black']}- ({record.funcName} - {record.filename}:{record.lineno}){COLORS['reset']}"
            )
        else:
            # Plain formatting without colors
            formatted = (
                f"{record.asctime} | "
                f"{record.levelname:<8} | "
                f"{record.name:<20} | "
                f"{record.getMessage()} "
                f"- ({record.funcName} - {record.filename}:{record.lineno})"
            )

        return formatted


# Global configuration
_initialized = False
_handler: logging.Handler | None = None
_root_logger: logging.Logger | None = None


def _initialize_logging() -> None:
    """Initialize the logging system (called lazily)."""
    global _initialized, _handler, _root_logger

    if _initialized:
        return

    # Create handler with custom formatter
    _handler = logging.StreamHandler()
    _handler.setFormatter(QiCustomFormatter())

    # Ensure UTF-8 encoding for emoji support
    if hasattr(_handler.stream, "reconfigure"):
        _handler.stream.reconfigure(encoding="utf-8")
    elif hasattr(_handler.stream, "buffer"):
        # For older Python versions
        import io

        _handler.stream = io.TextIOWrapper(_handler.stream.buffer, encoding="utf-8")

    # Configure root logger
    _root_logger = logging.getLogger()
    _root_logger.addHandler(_handler)

    # Set initial level from environment
    _set_level_from_env()

    _initialized = True


def _set_level_from_env() -> None:
    """Set logging level based on environment variables."""
    if not _initialized or not _handler or not _root_logger:
        return

    # Check environment variables
    qi_dev_mode = os.getenv("QI_DEV_MODE", "false").lower() == "true"
    qi_log_level = os.getenv("QI_LOG_LEVEL", "INFO").upper()

    level_map = {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
    }

    if qi_dev_mode:
        level = DEBUG
    else:
        level = level_map.get(qi_log_level, INFO)

    _handler.setLevel(level)
    _root_logger.setLevel(level)


def set_level(level: int) -> None:
    """
    Set the logging level.

    Args:
        level: Logging level (use constants like DEBUG, INFO, etc.)
    """
    _initialize_logging()
    if _handler and _root_logger:
        _handler.setLevel(level)
        _root_logger.setLevel(level)


def get_logger(name: str | None = None, level: int | None = None) -> logging.Logger:
    """
    Get a logger with custom formatting.

    Args:
        name: Logger name (typically __name__ from calling module)
        level: Optional override for logging level

    Returns:
        Configured logger instance

    Usage:
        log = get_logger(__name__)
        log.info("Hello world!")
    """
    _initialize_logging()

    if level is not None:
        set_level(level)

    return logging.getLogger(name)


def add_file_handler(
    filepath: str, level: int | None = None, use_colors: bool = False
) -> None:
    """
    Add a file handler to the root logger.

    Args:
        filepath: Path to log file
        level: Optional logging level for file handler
        use_colors: Whether to include ANSI colors in file output
    """
    _initialize_logging()

    if not _root_logger:
        return

    # Create file handler
    file_handler = logging.FileHandler(filepath, encoding="utf-8")
    file_handler.setFormatter(QiCustomFormatter(use_colors=use_colors))

    if level is not None:
        file_handler.setLevel(level)

    _root_logger.addHandler(file_handler)


def configure_logging(
    level: int | None = None,
    file_path: str | None = None,
    file_level: int | None = None,
) -> None:
    """
    Configure logging with console and optional file output.

    Args:
        level: Console logging level
        file_path: Optional file path for file logging
        file_level: Optional file logging level
    """
    if level is not None:
        set_level(level)

    if file_path:
        add_file_handler(file_path, file_level or level)


# Testing function
def _test_logger() -> None:
    """Test the logger formatting."""
    log = get_logger("TestLogger", level=DEBUG)
    log.debug("Testing debug level formatting..")
    log.info("Testing info level formatting..")
    log.warning("Testing warning level formatting..")
    log.error("Testing error level formatting..")
    log.critical("Testing critical level formatting..")


if __name__ == "__main__":
    _test_logger()
