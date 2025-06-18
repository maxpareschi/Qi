# hub/launcher.py
from app.launcher import qi_gui_launcher
from core.launch_config import qi_launch_config
from core.logger import get_logger

log = get_logger(__name__)

if __name__ == "__main__":
    log.info("Starting hub launcher")
    log.info("Loading config...")
    log.debug(
        f"Config loaded:\n{qi_launch_config.model_dump_json(indent=4)}",
    )

    if qi_launch_config.headless:
        log.warning(
            "Headless mode enabled, but no cli is available yet. TODO: Implement cli."
        )
    else:
        qi_gui_launcher()
