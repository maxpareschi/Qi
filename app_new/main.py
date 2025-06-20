# app_new/main.py

"""
Main entry point for Qi.

This module provides the main entry point for the Qi application.
"""

import sys

from app_new.application import Application
from core_new.config import app_config
from core_new.logger import get_logger

log = get_logger("main")


def main():
    """
    Main entry point for the application.
    """
    log.info("Starting Qi application...")
    log.debug(
        f"Config loaded: dev_mode={app_config.dev_mode}, server={app_config.server_host}:{app_config.server_port}"
    )

    try:
        app = Application()
        app.run()
    except KeyboardInterrupt:
        log.info("Application interrupted by user")
    except Exception as e:
        log.critical(f"Fatal error in application: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
