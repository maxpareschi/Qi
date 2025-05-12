import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.dev_proxy import dev_proxy

app = FastAPI()
if os.getenv("QI_DEV") == "1":
    app.middleware("http")(dev_proxy)

# mount static for prod builds
app.mount("/", StaticFiles(directory="addons", html=True), name="static")
