import argparse
import json
import os
import threading
import time

from dotenv import load_dotenv

from core import logger
from hub.lib.utils import get_addons, sanitize_server_address, update_env


def setup_qi(dev: bool = False, load_env: bool = True):
    """Setup Qi environment and return addons."""

    if load_env:
        load_dotenv()

    if dev:
        log = logger.get_logger(__name__, level=logger.DEBUG)
        log.debug("Development mode enabled!")
    else:
        log = logger.get_logger(__name__)

    # Get environment variables
    qi_local_server = os.getenv("QI_LOCAL_SERVER", None)
    qi_local_port = os.getenv("QI_LOCAL_PORT", None)
    qi_ssl_key_path = os.getenv("QI_SSL_KEY_PATH", None)
    qi_ssl_cert_path = os.getenv("QI_SSL_CERT_PATH", None)
    qi_addon_paths = os.getenv(
        "QI_ADDON_PATHS", os.path.abspath("addons").replace("\\", "/")
    )

    # Validate required environment variables
    if qi_local_server is None or qi_local_port is None:
        log.error("QI_LOCAL_SERVER and QI_LOCAL_PORT must be set")
        raise ValueError()

    # Update environment with sanitized values
    update_env(
        QI_LOCAL_SERVER=sanitize_server_address(qi_local_server),
        QI_LOCAL_PORT=int(qi_local_port),
        QI_SSL_KEY_PATH=qi_ssl_key_path,
        QI_SSL_CERT_PATH=qi_ssl_cert_path,
        QI_DEV_MODE=str(int(dev)),
        QI_ADDON_PATHS=qi_addon_paths,
    )

    # Log SSL configuration
    if qi_ssl_key_path and qi_ssl_cert_path:
        log.info(f"SSL enabled on https://{qi_local_server}:{qi_local_port}")
    else:
        log.info(
            f"SSL not configured, running on http://{qi_local_server}:{qi_local_port}"
        )

    addons = get_addons()

    update_env(QI_ADDONS=json.dumps(addons))

    qi_env_vars = [f"{k}: {v}" for k, v in os.environ.items() if k.startswith("QI_")]
    log.info(f"Environment setup complete: {qi_env_vars}")


server_process: threading.Thread | None = None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", help="Enable development mode")
    parser.add_argument(
        "--skip-env",
        action="store_true",
        help="Skip environment variables loading",
    )
    args = parser.parse_args()

    setup_qi(dev=args.dev, load_env=not args.skip_env)

    qi_local_server = os.getenv("QI_LOCAL_SERVER", "127.0.0.1")
    qi_local_port = int(os.getenv("QI_LOCAL_PORT", 8000))
    qi_ssl_key_path = os.getenv("QI_SSL_KEY_PATH", None)
    qi_ssl_cert_path = os.getenv("QI_SSL_CERT_PATH", None)
    qi_dev_mode = bool(int(os.getenv("QI_DEV_MODE", "0")))
    qi_addons = json.loads(os.getenv("QI_ADDONS", "\{\}"))

    from core.gui import setup_window_manager

    window_manager = setup_window_manager()

    from hub.lib.runners import run_server

    server_thread = run_server(
        qi_local_server, qi_local_port, qi_ssl_key_path, qi_ssl_cert_path, qi_dev_mode
    )

    # Wait a moment for server to initialize
    time.sleep(1)

    icon_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "static",
        "qi_512.png",
    ).replace("\\", "/")

    for addon_name, addon_data in qi_addons.items():
        window_manager.create_window(addon=addon_name, session_id="test-session")

    window_manager.run(
        icon=icon_path,
    )

    os._exit(0)
