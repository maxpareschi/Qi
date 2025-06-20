"""
Server Middleware for Qi.

This module provides middleware for the Qi server.
"""

import json
import os
import time
from pathlib import Path
from typing import Callable, Dict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, RedirectResponse

from core_new.config import app_config
from core_new.di import container
from core_new.logger import get_logger

log = get_logger("server.middleware")


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for authentication.

    This middleware checks for authentication tokens in requests.
    """

    def __init__(self, app: FastAPI, exclude_paths: list[str] = None):
        """
        Initialize the middleware.

        Args:
            app: The FastAPI application.
            exclude_paths: A list of paths to exclude from authentication.
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/ws",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process a request.

        Args:
            request: The request to process.
            call_next: The next middleware or route handler.

        Returns:
            The response from the next middleware or route handler.
        """
        # Skip authentication for excluded paths
        path = request.url.path
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return await call_next(request)

        # Check for authentication token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

        # Extract the token
        token = auth_header.split(" ")[1]

        # Validate the token
        try:
            db_manager = container.get("db_manager")
            user_info = await db_manager.validate_token(token)

            # Add user info to request state
            request.state.user = user_info.get("user", {})
            request.state.token = token

            # Continue with the request
            return await call_next(request)
        except Exception as e:
            log.error(f"Authentication error: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication token"},
            )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging requests.

    This middleware logs information about requests and responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process a request.

        Args:
            request: The request to process.
            call_next: The next middleware or route handler.

        Returns:
            The response from the next middleware or route handler.
        """
        start_time = time.time()

        # Log the request
        log.debug(
            f"Request: {request.method} {request.url.path} "
            f"(client: {request.client.host if request.client else 'unknown'})"
        )

        # Process the request
        response = await call_next(request)

        # Log the response
        duration = time.time() - start_time
        log.debug(f"Response: {response.status_code} (duration: {duration:.3f}s)")

        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling errors.

    This middleware catches exceptions and returns appropriate error responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process a request.

        Args:
            request: The request to process.
            call_next: The next middleware or route handler.

        Returns:
            The response from the next middleware or route handler.
        """
        try:
            return await call_next(request)
        except Exception as e:
            log.error(f"Unhandled exception: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )


class DevProxyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for proxying requests to development servers.

    In development mode, this middleware intercepts requests to certain paths
    and redirects them to development servers.
    """

    def __init__(self, app: FastAPI, dev_servers: Dict[str, Dict[str, str]]):
        """
        Initialize the middleware.

        Args:
            app: The FastAPI application.
            dev_servers: A dictionary mapping addon names to development server URLs.
        """
        super().__init__(app)
        self.dev_servers = dev_servers
        log.info(f"DevProxyMiddleware initialized with dev servers: {dev_servers}")

    async def dispatch(self, request: Request, call_next):
        """
        Dispatch the request.

        Args:
            request: The incoming request.
            call_next: The next middleware in the chain.

        Returns:
            The response.
        """
        path = request.url.path
        for addon_name, server_info in self.dev_servers.items():
            if path.startswith(f"/{addon_name}"):
                # Get the server URL
                server_url = server_info.get("url", "")
                if not server_url:
                    continue

                # Build the target URL
                target_url = f"{server_url}{path}"
                if request.query_params:
                    target_url += f"?{request.query_params}"

                log.debug(f"Proxying request to: {target_url}")
                return RedirectResponse(target_url)

        return await call_next(request)


class StaticFilesMiddleware(BaseHTTPMiddleware):
    """
    Middleware for serving static files.

    This middleware serves static files from addon UI directories.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Dispatch the request.

        Args:
            request: The incoming request.
            call_next: The next middleware in the chain.

        Returns:
            The response.
        """
        path = request.url.path
        if path.startswith("/ui/"):
            # Remove the /ui/ prefix
            parts = path.split("/")
            if len(parts) < 3:
                # This is just /ui/, serve the main UI
                ui_path = (
                    Path(app_config.base_path)
                    / "addons"
                    / "addon-skeleton"
                    / "ui-dist"
                    / "index.html"
                )
                if ui_path.exists():
                    return FileResponse(str(ui_path))
                return await call_next(request)

            # Get the addon name
            addon_name = parts[2]

            # Build the file path
            file_path_parts = parts[3:]
            file_path = Path(app_config.base_path) / "addons" / addon_name / "ui-dist"
            if file_path_parts:
                file_path = file_path.joinpath(*file_path_parts)
            else:
                file_path = file_path / "index.html"

            # If file exists, serve it
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))

            # If it's a directory, serve index.html
            if file_path.exists() and file_path.is_dir():
                index_path = file_path / "index.html"
                if index_path.exists():
                    return FileResponse(str(index_path))

            # If file not found, try index.html (SPA routing)
            index_path = (
                Path(app_config.base_path)
                / "addons"
                / addon_name
                / "ui-dist"
                / "index.html"
            )
            if index_path.exists():
                return FileResponse(str(index_path))

        return await call_next(request)


def add_middleware(app: FastAPI) -> None:
    """
    Add middleware to a FastAPI application.

    Args:
        app: The FastAPI application.
    """
    # Add middleware in reverse order (last added is executed first)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthenticationMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add development proxy middleware in dev mode
    if app_config.dev_mode:
        dev_servers = app_config.addon_dev_servers
        if not dev_servers and "QI_DEV_SERVERS" in os.environ:
            try:
                dev_servers = json.loads(os.environ["QI_DEV_SERVERS"])
            except json.JSONDecodeError:
                log.error("Failed to parse QI_DEV_SERVERS environment variable")
                dev_servers = {}

        if dev_servers:
            app.add_middleware(DevProxyMiddleware, dev_servers=dev_servers)
            log.info("Added DevProxyMiddleware")

    # Add static files middleware
    app.add_middleware(StaticFilesMiddleware)
    log.info("Added StaticFilesMiddleware")
