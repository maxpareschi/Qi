#!/usr/bin/env python3
"""
Launcher Script for Qi.

This script provides a command-line interface for launching the Qi application
in different modes.
"""

import argparse
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the app package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app_new.main import main
from core_new.config import app_config
from core_new.logger import get_logger, setup_logging

log = get_logger("launcher")


def parse_args():
    """
    Parse command-line arguments.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Qi Application Launcher")

    # Basic options
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run in development mode",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (no UI)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Set the logging level",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="Directory for log files",
    )

    # Server options
    parser.add_argument(
        "--host",
        default=None,
        help="Server hostname",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server port",
    )

    # Bundle options
    parser.add_argument(
        "--bundle",
        default=None,
        help="Name of the bundle to activate",
    )

    # Advanced options
    parser.add_argument(
        "--config",
        default=None,
        help="Path to the configuration file",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Path to the data directory",
    )
    parser.add_argument(
        "--addon-path",
        action="append",
        dest="addon_paths",
        default=[],
        help="Path to addon directories (can be specified multiple times)",
    )

    return parser.parse_args()


def apply_args_to_config(args):
    """
    Apply command-line arguments to the application configuration.

    Args:
        args: The parsed command-line arguments.
    """
    # Apply basic options
    if args.dev:
        app_config.dev_mode = True
    if args.headless:
        app_config.headless = True
    if args.log_level:
        app_config.log_level = args.log_level

    # Apply server options
    if args.host:
        app_config.server_host = args.host
    if args.port:
        app_config.server_port = args.port

    # Apply bundle options
    if args.bundle:
        app_config.default_bundle_name = args.bundle

    # Apply advanced options
    if args.config:
        app_config.config_file = args.config
    if args.data_dir:
        app_config.data_dir = args.data_dir
    if args.addon_paths:
        app_config.addon_paths.extend(args.addon_paths)

    # Set up logging
    if args.log_dir:
        setup_logging(args.log_dir, app_config.log_level)
    else:
        setup_logging(log_level=app_config.log_level)


if __name__ == "__main__":
    # Parse arguments
    args = parse_args()

    # Apply arguments to configuration
    apply_args_to_config(args)

    # Run the application
    sys.exit(main())
