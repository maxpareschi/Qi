import argparse
import os
import threading
import time

from dotenv import load_dotenv

from core import logger
from hub.lib.utils import get_dev_servers, sanitize_server_address, update_env

load_dotenv()

server_process: threading.Thread | None = None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()

    qi_local_server = sanitize_server_address(os.getenv("QI_LOCAL_SERVER", "127.0.0.1"))
    qi_local_port = int(os.getenv("QI_LOCAL_PORT", 8000))
    qi_ssl_key_path = os.getenv("QI_SSL_KEY_PATH", None)
    qi_ssl_cert_path = os.getenv("QI_SSL_CERT_PATH", None)
    qi_dev_mode = args.dev

    update_env(
        QI_LOCAL_SERVER=qi_local_server,
        QI_LOCAL_PORT=qi_local_port,
        QI_SSL_KEY_PATH=qi_ssl_key_path,
        QI_SSL_CERT_PATH=qi_ssl_cert_path,
        QI_DEV_MODE=str(int(qi_dev_mode)),
    )

    log = logger.get_logger(__name__)

    addon_paths = os.listdir("addons")  # to be replaced with addon manager call
    addon_urls = dict()

    if qi_dev_mode:
        addon_urls = get_dev_servers(qi_local_server, target_servers=len(addon_paths))
    else:
        protocol = "https" if qi_ssl_key_path and qi_ssl_cert_path else "http"
        for addon_name in addon_paths:
            addon_urls[addon_name] = (
                f"{protocol}://{qi_local_server}:{qi_local_port}/{addon_name}"
            )

    update_env(QI_ADDONS=addon_urls)

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

    for addon_name, url in addon_urls.items():
        window_manager.create_window(addon=addon_name, session="test-session")

    window_manager.run(
        icon=icon_path,
    )

    os._exit(0)
