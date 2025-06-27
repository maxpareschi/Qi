"""
Logger for Qi.

This module provides a logging system for the application.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Optional

from core_new.config import app_config

# Configure the root logger
root_logger = logging.getLogger()

# Create a formatter for console output
console_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Create a formatter for file output (more detailed)
file_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Create console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(console_formatter)

# Add the console handler to the root logger
root_logger.addHandler(console_handler)

# Cache for loggers
_loggers: Dict[str, logging.Logger] = {}


def setup_logging(
    log_dir: Optional[str] = None, log_level: Optional[str] = None
) -> None:
    """
    Set up logging for the application.

    Args:
        log_dir: Directory to store log files. If None, logs are only output to console.
        log_level: The log level to use. If None, use the level from app_config.
    """
    level = log_level or app_config.log_level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Set up file logging if a directory is provided
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        log_file = log_path / "qi.log"
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        root_logger.info(f"Logging to file: {log_file}")

    # Reset the cache
    _loggers.clear()

    root_logger.info(f"Logging initialized at level {level}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    This function returns a cached logger if one exists, or creates a new one.
    The logger inherits the configuration from the root logger.

    Args:
        name: The name of the logger

    Returns:
        A configured logger
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    _loggers[name] = logger
    return logger


# Initialize logging with default settings
setup_logging()
