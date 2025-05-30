# hub/launcher.py

import argparse

from core.config import config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch Qi app.")
    parser.add_argument("--dev_mode", action="store_true", help="Enable dev mode")
    parser.add_argument("--local_server", type=str, help="Override local server")
    parser.add_argument("--local_port", type=int, help="Override local port")
    parser.add_argument("--log_level", type=str, help="Override log level")
    parser.add_argument("--ssl_cert_path", type=str, help="Override SSL cert path")
    parser.add_argument("--ssl_key_path", type=str, help="Override SSL key path")

    cli_flags = parser.parse_args().__dict__
    if cli_flags.get("dev_mode"):
        cli_flags["log_level"] = "DEBUG"

    for key, value in cli_flags.items():
        if value is not None:
            setattr(config, key, value)

    print(config)

    # Now that env is fully set, import config and run
    # import core.main

    # core.main.run()
