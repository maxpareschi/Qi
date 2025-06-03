import json
import mimetypes
import os
from pathlib import Path

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, RedirectResponse

from core.logger import get_logger

log = get_logger(__name__)


class QiDevProxyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for development mode to proxy addon requests to their respective dev servers.

    This middleware intercepts requests whose paths start with an addon name
    (as defined in the `QI_ADDONS` environment variable, which should be a JSON string
    mapping addon names to their dev server URLs).
    It then redirects the request to `dev_server_url/actual_path?original_query_params`.
    This is useful for developing UI addons with hot-reloading development servers.
    """

    async def dispatch(self, request: Request, call_next):
        """Proxies requests to addon development servers if applicable."""
        dev_servers: dict[str, dict[str, str]] = json.loads(
            os.getenv("QI_ADDONS", json.dumps({}))
        )
        for addon_name, addon_data in dev_servers.items():
            if request.url.path.startswith(f"/{addon_name}"):
                # Construct the target URL carefully, preserving the full original path.
                # Example: request for /addon_name/some/page -> dev_server_url/addon_name/some/page
                base_dev_url = addon_data["url"].rstrip("/")
                # request.url.path already includes the leading /addon_name
                target_url = f"{base_dev_url}{request.url.path}"

                if request.query_params:
                    target_url += f"?{request.query_params}"
                log.info(f"Proxying request for '{request.url.path}' to '{target_url}'")
                return RedirectResponse(url=target_url)

        return await call_next(request)


class QiSPAStaticFilesMiddleware(BaseHTTPMiddleware):
    """
    Middleware to serve static files for Single Page Application (SPA) addons.

    This middleware handles requests for addon UI resources in a production-like setup:
    1. It checks if the request path corresponds to an existing addon's UI directory
       (e.g., `addons/addon_name/ui/`).
    2. If a specific file is requested (e.g., `/addon_name/main.js`) and exists within
       the addon's UI directory, it's served with the appropriate MIME type.
    3. If a path looks like a client-side route (e.g., `/addon_name/some/route` - no extension),
       or if a directory is requested, it serves the `index.html` from that addon's UI directory,
       allowing client-side routing to handle the request.
    4. Includes a basic check to prevent directory traversal.
    5. Bypasses non-addon paths (e.g., `/ws`, `/api/`, `/favicon.ico`).
    """

    async def dispatch(self, request: Request, call_next):
        """Serves SPA static files or index.html for addon routes."""
        path_str = request.url.path.lstrip("/")

        # Skip non-addon paths, API calls, WebSocket connections, etc.
        if (
            not path_str
            or path_str == "favicon.ico"
            or path_str.startswith("api/")
            or path_str.startswith("ws/")
        ):
            return await call_next(request)

        parts = path_str.split("/", 1)
        addon_name = parts[0]

        addon_ui_dir = Path(f"addons/{addon_name}/ui-dist").resolve()  # Resolve early
        if not addon_ui_dir.is_dir():
            return await call_next(request)

        # Determine the path relative to the addon_ui_dir
        relative_path_str = parts[1] if len(parts) > 1 and parts[1] else "index.html"

        try:
            # Safely join and resolve the path
            file_path = addon_ui_dir.joinpath(relative_path_str).resolve()
            # Security check: Ensure the resolved path is still within the addon's UI directory
            if not str(file_path).startswith(str(addon_ui_dir)):
                log.warning(
                    f"Potential directory traversal attempt: '{relative_path_str}' for addon '{addon_name}'"
                )
                return await call_next(request)  # Or a 403/404 response
        except Exception as e:
            log.warning(
                f"Error resolving path '{relative_path_str}' for addon '{addon_name}': {e}"
            )
            return await call_next(request)  # Or a 404 response

        # If the resolved path points to a directory, try serving index.html from it
        if file_path.is_dir():
            file_path = file_path / "index.html"

        # If the original request path didn't have an extension (likely a client-side route)
        # and the resolved file_path isn't an existing file, default to serving index.html.
        # This covers cases like /addon_name/some/route -> /addon_name/ui/index.html
        has_extension = "." in Path(relative_path_str).name
        if not has_extension and not file_path.is_file():
            file_path = addon_ui_dir / "index.html"

        if file_path.is_file():
            content_type, _ = mimetypes.guess_type(str(file_path))
            if content_type and (
                content_type.startswith("text/")
                or content_type == "application/javascript"
            ):
                content_type += "; charset=utf-8"
            return FileResponse(str(file_path), media_type=content_type or "text/plain")

        return await call_next(request)
