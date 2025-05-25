import argparse
import os
import threading
import time

from dotenv import load_dotenv

from hub.lib.runners import run_server
from hub.lib.utils import (
    get_dev_servers,
    sanitize_server_address,
    set_dev_mode,
    update_env,
)

load_dotenv()

server_process: threading.Thread | None = None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()

    qi_dev_mode = set_dev_mode(args.dev)
    qi_local_server = sanitize_server_address(os.getenv("QI_LOCAL_SERVER", "127.0.0.1"))
    qi_local_port = int(os.getenv("QI_LOCAL_PORT", 8000))
    qi_ssl_key_path = os.getenv("QI_SSL_KEY_PATH", "").replace("\\", "/")
    qi_ssl_cert_path = os.getenv("QI_SSL_CERT_PATH", "").replace("\\", "/")

    update_env(
        QI_LOCAL_SERVER=qi_local_server,
        QI_LOCAL_PORT=qi_local_port,
        QI_SSL_KEY_PATH=qi_ssl_key_path,
        QI_SSL_CERT_PATH=qi_ssl_cert_path,
        QI_DEV_MODE=int(qi_dev_mode),
    )

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

    # IMPORTANT: Get the connection manager instance BEFORE starting the server
    # This ensures we use the same instance
    print(f"Launcher.py: Connection manager instance ID: {id(connection_manager)}")

    # Create and bind the window manager
    window_manager = QiWindowManager()
    bind_window_manager_to_bus(window_manager)

    # Verify handler registration
    print("Launcher.py: Registered handlers:")
    connection_manager.list_handlers()  # Should show registered handlers

    # Now start the server
    server_process = run_server(qi_local_server, qi_local_port)

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

    if server_process and server_process.poll() is None:
        server_process.terminate()

    os._exit(0)
