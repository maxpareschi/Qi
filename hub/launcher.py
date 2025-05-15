import argparse
import os
import threading

import webview
from dotenv import load_dotenv

from core.log import log
from hub.runners import run_server
from hub.utils import (
    WebViewControlApi,
    get_dev_servers,
    sanitize_server_address,
    set_dev_mode,
    update_env,
)

load_dotenv()

_windows: dict[str, webview.Window] = {}
_server_process: threading.Thread | None = None


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

    _server_process = run_server(qi_local_server, qi_local_port)

    for addon_name, url in addon_urls.items():
        _windows[addon_name] = webview.create_window(
            addon_name,
            url=url,
            min_size=(350, 250),
            width=800,
            height=600,
            x=500,
            y=300,
            js_api=WebViewControlApi(),
            background_color="#222222",
            frameless=True,
            easy_drag=False,
        )

        log.debug(
            f"Activated webviews: {[win.title + ' | ' + url + ' | ' + win.uid for win in webview.windows]}"
        )

    icon_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "static",
        "qi_512.png",
    ).replace("\\", "/")

    log.info(f"Icon path: {icon_path}")

    webview.start(
        icon=icon_path,
        debug=qi_dev_mode,
    )

    if _server_process and _server_process.poll() is None:
        _server_process.terminate()

    os._exit(0)
