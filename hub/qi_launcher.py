import argparse
import os

import uvicorn
import webview

from core.server import app


def bootstrap():
    uvicorn.run(app, loop="asyncio", port=8000, log_level="warning", reload=False)


parser = argparse.ArgumentParser()
parser.add_argument("--dev", action="store_true")
args = parser.parse_args()
os.environ["QI_DEV"] = "1" if args.dev else "0"

webview.create_window("Qi Hub", url="http://127.0.0.1:8000/tray_icon/")
webview.start(func=bootstrap)
