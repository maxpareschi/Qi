# app/main.py

"""
This module contains the main entry point for the Qi system.
"""

from app.launcher import QiApplication
from core.config import qi_launch_config
from core.logger import get_logger

log = get_logger(__name__)

if __name__ == "__main__":
    log.info("Starting Qi Application...")
    log.debug(
        f"Config loaded:\n{qi_launch_config.model_dump_json(indent=4)}",
    )

    if qi_launch_config.headless:
        log.warning(
            "Headless mode enabled, but no cli is available yet. TODO: Implement cli."
        )
    else:
        app = QiApplication()
        app.run()
