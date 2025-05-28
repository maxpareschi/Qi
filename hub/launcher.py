import argparse
import json
import os
import threading

from core.gui import QiWindowManager, bind_window_manager
from hub.lib.utils import setup_qi_env

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

    setup_qi_env(dev=args.dev, load_env=(not args.skip_env))

    qi_local_server: str = os.getenv("QI_LOCAL_SERVER", "127.0.0.1")
    qi_local_port: int = int(os.getenv("QI_LOCAL_PORT", 8000))
    qi_ssl_key_path: str | None = os.getenv("QI_SSL_KEY_PATH", None)
    qi_ssl_cert_path: str | None = os.getenv("QI_SSL_CERT_PATH", None)
    qi_dev_mode: bool = bool(int(os.getenv("QI_DEV_MODE", "0")))
    qi_addons: dict[str, dict] = json.loads(os.getenv("QI_ADDONS", json.dumps({})))

    window_manager = QiWindowManager()
    bind_window_manager(window_manager)

    from hub.lib.runners import run_server

    server_thread = run_server(
        qi_local_server,
        qi_local_port,
        qi_ssl_key_path,
        qi_ssl_cert_path,
        qi_dev_mode,
    )

    # Wait a moment for server to initialize
    # time.sleep(1)

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
