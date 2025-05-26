import json
import mimetypes
import os
from pathlib import Path

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, RedirectResponse

from core import logger

log = logger.get_logger(__name__)


class QiDevProxyMiddleware(BaseHTTPMiddleware):
    """Middleware to proxy requests to development servers in dev mode"""

    async def dispatch(self, request: Request, call_next):
        if dev_servers := json.loads(os.getenv("QI_ADDONS", "{}")):
            for addon_name, addon_data in dev_servers.items():
                log.debug(
                    f'Name: "{addon_name}", URL: "{addon_data["url"]}", REQUEST: "{request.url.path}", PARAMS: "{request.query_params}"'
                )
                if request.url.path.startswith(f"/{addon_name}"):
                    return RedirectResponse(
                        url=f"{addon_data['url']}/{addon_name}?{request.query_params}"
                    )

        return await call_next(request)


class QiSPAStaticFilesMiddleware(BaseHTTPMiddleware):
    """Middleware to serve static files and handle SPA routing for addons"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.lstrip("/")

        # Skip non-addon paths
        if not path or path == "favicon.ico" or path.startswith("ws/"):
            return await call_next(request)

        # Extract addon name from the path
        parts = path.split("/", 1)
        addon_name = parts[0]

        # Check if addon exists
        addon_dir = Path(f"addons/{addon_name}/ui")
        if not addon_dir.exists():
            return await call_next(request)

        # Determine the file path
        if len(parts) > 1:
            file_path = addon_dir / parts[1]
        else:
            file_path = addon_dir / "index.html"

        # If the path doesn't have an extension and doesn't exist, serve index.html
        if "." not in file_path.name and not file_path.exists():
            file_path = addon_dir / "index.html"

        # If file exists, serve it
        if file_path.exists() and file_path.is_file():
            # Get the MIME type based on the file extension
            content_type, _ = mimetypes.guess_type(str(file_path))
            return FileResponse(str(file_path), media_type=content_type)

        # For asset files that don't exist, pass to the next middleware
        if "." in parts[-1] if len(parts) > 1 else False:
            return await call_next(request)

        # For SPA routes, serve index.html
        index_path = addon_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))

        # If nothing matches, pass to the next middleware
        return await call_next(request)
