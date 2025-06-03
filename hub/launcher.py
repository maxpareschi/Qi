import os
import threading

from core.config import qi_config
from hub.lib.runners import run_server


def qi_gui_launcher():
    """
    Launcher for the hub.
    """
    # window_manager = QiWindowManager()
    # bind_window_manager(window_manager)

    server_thread: threading.Thread = run_server(
        qi_config.host,
        qi_config.port,
        qi_config.ssl_key_path,
        qi_config.ssl_cert_path,
        qi_config.dev_mode,
    )

    # icon_path = os.path.join(
    #     os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    #     "static",
    #     "qi_512.png",
    # ).replace("\\", "/")
    # for addon_name, addon_data in qi_config.addon_paths.items():
    #     window_manager.create_window(addon=addon_name, session_id="test-session")
    # window_manager.run(
    #     icon=icon_path,
    # )

    server_thread.join()

    os._exit(0)
