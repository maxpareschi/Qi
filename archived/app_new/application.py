"""
Application Class for Qi.

This module provides the main application class that orchestrates the entire
application lifecycle.
"""

import asyncio
import signal
import sys

from core_new.abc import ManagerBase
from core_new.addon.manager import AddonManager
from core_new.bundle.manager import BundleManager
from core_new.config import app_config
from core_new.db.bus_handlers import register_db_handlers
from core_new.db.manager import DatabaseManager
from core_new.di import container
from core_new.gui.window_manager import WindowManager
from core_new.logger import get_logger
from core_new.messaging.bus import MessageBus
from core_new.messaging.hub import Hub
from core_new.server.middleware import add_middleware
from core_new.server.server import ServerManager
from core_new.server.settings_routes import create_settings_router
from core_new.settings.bus_handlers import register_settings_handlers
from core_new.settings.manager import SettingsManager

log = get_logger("application")


class Application:
    """
    Main application class for Qi.

    This class orchestrates the initialization, running, and shutdown of all
    core services and managers.
    """

    def __init__(self):
        """Initialize the application."""
        log.info("Initializing Qi application...")
        self._setup_signal_handlers()
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._shutdown_task = None  # Track shutdown task

        # Define the order of manager initialization and shutdown
        self._manager_names = [
            "db_manager",
            "bundle_manager",
            "addon_manager",
            "settings_manager",
            "server_manager",
            "window_manager",
        ]

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        if sys.platform != "win32":  # SIGTERM is not supported on Windows
            signal.signal(signal.SIGTERM, self._handle_exit_signal)
        signal.signal(signal.SIGINT, self._handle_exit_signal)

    def _handle_exit_signal(self, signum, frame):
        """Handle exit signals."""
        log.info(f"Received signal {signum}, initiating shutdown...")
        if self._running and not self._shutdown_task:
            self._shutdown_task = asyncio.create_task(self.shutdown())

    def _register_services(self):
        """Register all services with the DI container."""
        log.info("Registering services...")

        # Core messaging (Hub is not a full manager, but needs registration)
        message_bus = MessageBus()
        hub = Hub(message_bus)
        container.register_instance("hub", hub)
        container.register_instance("message_bus", message_bus)

        # Register all managers
        container.register_singleton("addon_manager", lambda: AddonManager())
        container.register_singleton("bundle_manager", lambda: BundleManager())
        container.register_singleton("db_manager", lambda: DatabaseManager())
        container.register_singleton("settings_manager", lambda: SettingsManager())
        container.register_singleton("server_manager", lambda: ServerManager())
        container.register_singleton("window_manager", lambda: WindowManager())

        # After all services are registered, register the bus handlers that use them
        register_db_handlers()
        register_settings_handlers()

        log.info("All services registered.")

    async def _initialize_managers(self):
        """Initialize all registered managers in order."""
        log.info("Initializing managers...")

        # Get managers that need special handling first
        addon_manager = container.get_typed("addon_manager", AddonManager)
        db_manager = container.get_typed("db_manager", DatabaseManager)
        bundle_manager = container.get_typed("bundle_manager", BundleManager)

        # --- Bundle Initialization ---
        # Bundles must be initialized before addons to apply environment variables
        await bundle_manager.initialize()
        bundle_manager.apply_bundle_env()

        # --- Addon Initialization & Provider Wiring ---
        # Discover and load all addons. The manager will handle loading
        # internal providers and letting external addons override them.
        addon_manager.discover_addons(app_config.addon_paths)
        addon_manager.load_provider_addons()

        # Wire up the DB and Auth providers from the manager
        auth_provider = addon_manager.get_provider("auth")
        db_provider = addon_manager.get_provider("db")

        # Validate that providers exist and have valid services
        if not auth_provider:
            raise RuntimeError("No auth provider found")
        if not db_provider:
            raise RuntimeError("No db provider found")

        auth_service = auth_provider.get_service()
        db_service = db_provider.get_service()

        if not auth_service:
            raise RuntimeError(
                f"Auth provider '{auth_provider.name}' returned None service"
            )
        if not db_service:
            raise RuntimeError(
                f"DB provider '{db_provider.name}' returned None service"
            )

        # Set the adapters on the DatabaseManager
        db_manager.set_auth_adapter(auth_service)
        db_manager.set_file_adapter(db_service)
        log.info("Auth and DB adapters have been set on the DatabaseManager.")

        # --- Remaining Manager Initialization ---
        # Initialize all other managers
        remaining_managers = [
            name
            for name in self._manager_names
            if name not in ("addon_manager", "db_manager", "bundle_manager")
        ]
        for name in remaining_managers:
            try:
                manager = container.get_typed(name, ManagerBase)
                log.debug(f"Initializing {name}...")
                await manager.initialize()
            except Exception as e:
                log.critical(
                    f"Failed to initialize manager '{name}': {e}", exc_info=True
                )
                raise

        # --- Final Addon Loading ---
        # Now that all managers are initialized, load the regular addons
        addon_manager.load_regular_addons()

        log.info("Managers initialized successfully.")

    async def _start_managers(self):
        """Start all registered managers in order."""
        log.info("Starting managers...")
        for name in self._manager_names:
            try:
                manager = container.get_typed(name, ManagerBase)
                log.debug(f"Starting {name}...")
                await manager.start()
            except Exception as e:
                log.critical(f"Failed to start manager '{name}': {e}", exc_info=True)
                raise
        log.info("Managers started successfully.")

    async def _configure_server(self):
        """Add routes and middleware to the server."""
        server_manager = container.get_typed("server_manager", ServerManager)
        settings_router = create_settings_router()
        server_manager.add_router(settings_router)
        add_middleware(server_manager.app)

    async def _create_main_window(self):
        """Create the main application window."""
        log.info("Creating main window...")
        window_manager = container.get_typed("window_manager", WindowManager)
        # The main window is hosted by the 'addon-skeleton' UI
        await window_manager.open_window(
            url="/ui/addon-skeleton", window_id="main_window"
        )

    async def initialize(self):
        """Initialize the application."""
        try:
            log.info("--- Qi Application Initializing ---")
            self._register_services()
            await self._initialize_managers()
            await self._configure_server()
            log.info("--- Qi Application Initialization Complete ---")
        except Exception as e:
            log.critical(f"Application initialization failed: {e}", exc_info=True)
            await self.shutdown()
            raise

    async def run_async(self):
        """Run the application asynchronously."""
        await self.initialize()
        self._running = True

        # Start managers
        await self._start_managers()

        # Create the main window if not in headless mode
        if not app_config.headless:
            await self._create_main_window()

        # Run until shutdown is requested
        log.info("Qi application is running...")
        await self._shutdown_event.wait()

    def run(self):
        """Run the application synchronously."""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            log.info("Application interrupted by user")
        except Exception as e:
            log.critical(f"Fatal error in application: {e}", exc_info=True)
            sys.exit(1)

    async def shutdown(self):
        """Shutdown the application."""
        if not self._running:
            return

        log.info("--- Qi Application Shutting Down ---")
        self._running = False  # Prevent re-entry

        try:
            # Shutdown managers in reverse order
            for name in reversed(self._manager_names):
                try:
                    manager = container.get_typed(name, ManagerBase)
                    log.debug(f"Shutting down {name}...")
                    await manager.shutdown()
                except Exception as e:
                    log.error(
                        f"Error during shutdown of manager '{name}': {e}", exc_info=True
                    )

        except Exception as e:
            log.error(f"Error during shutdown sequence: {e}", exc_info=True)
        finally:
            self._shutdown_event.set()
            log.info("--- Qi Application Shutdown Complete ---")
