# app/launcher.py

"""
This module contains the main application class for the Qi system.
"""

import asyncio
import os

from app.runners import run_server
from core.addon.manager import qi_addon_manager
from core.bundle.manager import qi_bundle_manager
from core.config import qi_launch_config
from core.constants import BASE_PATH
from core.gui.window_manager import qi_window_manager
from core.logger import get_logger
from core.settings.bus_handlers import register_settings_handlers
from core.settings.manager import qi_settings_manager

log = get_logger(__name__)


class QiApplication:
    """
    The main application class. Orchestrates the startup, running, and
    shutdown of all core services and managers.
    """

    def __init__(self):
        log.info("Qi application is initializing...")
        self._server_thread = None
        self.main_window_icon: str | None = None

    def _apply_bundle_env(self):
        """
        Applies the environment variables from the active bundle to the current process.
        """
        active_bundle = qi_bundle_manager.get_active_bundle()
        bundle_env = active_bundle.env
        if not bundle_env:
            log.info("No environment variables to apply for the active bundle.")
            return

        log.info(
            f"Applying environment variables for bundle '{active_bundle.name}': {bundle_env}"
        )
        os.environ.update(bundle_env)

    def _initialize_addons(self):
        """
        Discovers and loads all addons in two phases.
        This will automatically load and register the 'db' and 'auth'
        provider addons first, making them available for all other addons.
        """
        qi_addon_manager.discover_addons(qi_launch_config.addon_paths)

        # Phase 1: Load provider addons (auth, db)
        qi_addon_manager.load_provider_addons()
        log.info("Provider addons loaded successfully.")

        # TODO: Authentication handshake would happen here

        # Phase 2: Load regular addons
        qi_addon_manager.load_regular_addons()
        log.info("Regular addons loaded successfully.")

    async def _initialize_settings(self):
        """
        Builds the effective settings and registers handlers.
        """
        await qi_settings_manager.build_settings()
        register_settings_handlers()
        log.info("Settings manager initialized.")

    def _start_server(self):
        """
        Starts the Uvicorn server in a separate thread.
        """
        self._server_thread = run_server(
            qi_launch_config.host,
            qi_launch_config.port,
            qi_launch_config.ssl_key_path,
            qi_launch_config.ssl_cert_path,
            qi_launch_config.dev_mode,
        )
        log.info(
            f"FastAPI server started on http://{qi_launch_config.host}:{qi_launch_config.port}"
        )

    def _create_main_window(self):
        """
        Creates the main application window.
        """
        self.main_window_icon = os.path.join(
            BASE_PATH,
            "resources",
            "qi-icons",
            "qi_512.png",
        ).replace("\\", "/")

        qi_window_manager.create_window(
            addon="addon-skeleton", session_id="main-session"
        )

    def start(self):
        """
        Starts all services in the correct order.
        """
        try:
            log.info("--- Qi Application Starting ---")
            self._apply_bundle_env()
            self._initialize_addons()
            asyncio.run(self._initialize_settings())
            self._start_server()
            self._create_main_window()
            log.info("--- Qi Application Startup Complete ---")
        except Exception as e:
            log.critical(f"Application startup failed: {e}", exc_info=True)
            self.stop()
            raise

    def run(self):
        """
        Starts the application and enters the main GUI loop.
        """
        self.start()
        log.info("Entering main window event loop...")
        qi_window_manager.run(icon=self.main_window_icon)
        # This part is blocking. Code after this will run on shutdown.
        self.stop()

    def stop(self):
        """
        Gracefully shuts down all application services.
        """
        log.info("--- Qi Application Shutting Down ---")
        qi_addon_manager.close_all()
        log.info("All addons closed.")
        # The server thread is a daemon, so it will exit with the main process.
        log.info("--- Qi Application Shutdown Complete ---")
