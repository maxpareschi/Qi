# hub/launcher.py
from core.launch_config import qi_launch_config
from core.logger import get_logger
from hub.launcher import qi_gui_launcher

log = get_logger(__name__)

if __name__ == "__main__":
    log.info("Starting hub launcher")
    log.info("Loading config...")
    log.debug(
        f"Config loaded:\n{qi_launch_config.model_dump_json(indent=4)}",
    )
    log.info("Starting Main process...")
    log.debug("Main process started")

    if qi_launch_config.headless:
        log.warning("Headless mode enabled, but no cli is available now!")
    else:
        qi_gui_launcher()
