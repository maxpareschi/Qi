"""
Example Extension for Qi.

This extension demonstrates the basic extension structure and capabilities:
- Dependency injection with @inject
- Event handling with @subscribe
- Extension points with @extends
- Lifecycle management
"""

from typing import TYPE_CHECKING

from core.decorators import extends, inject, subscribe
from core.extension import QiExtensionBase
from core.logger import get_logger

if TYPE_CHECKING:
    from core.config import QiLaunchConfig
    from core.hub import Hub


@inject()
class ExampleExtension(QiExtensionBase):
    """
    A demonstration extension showing all major features.
    """

    # Dependencies auto-injected by Hub based on attribute names
    config: "QiLaunchConfig"
    hub: "Hub"

    def __init__(self):
        """Initialize the extension."""
        # Dependencies auto-injected by Hub after registration
        self.logger = get_logger(self.__class__.__name__)
        self._initialized = False

    def discover(self):
        """
        Discovery phase - called when extension is first loaded.
        Use this for one-time setup that doesn't depend on other services.
        """
        self.logger.info("Example extension discovered")

    def register(self):
        """
        Registration phase - called after all extensions are loaded.
        Use this to register services, handlers, or other functionality.
        """
        self.logger.info("Example extension registering...")

        # Register event handlers for Hub events
        if self.hub:
            self.hub.subscribe("app.startup", self.on_app_startup)
            self.hub.subscribe("app.shutdown", self.on_app_shutdown)

        self.logger.info("Example extension registered")

    def initialize(self):
        """
        Initialization phase - called when the application starts.
        Use this for initialization that depends on all extensions being loaded.
        """
        self.logger.info("Example extension initializing...")

        if self.config:
            dev_mode = getattr(self.config, "dev_mode", False)
            self.logger.info(f"Running in dev mode: {dev_mode}")

        self._initialized = True
        self.logger.info("Example extension initialized")

    def close(self):
        """
        Cleanup phase - called during application shutdown.
        Use this to cleanup resources, save state, etc.
        """
        self.logger.info("Example extension closing...")
        self._initialized = False
        self.logger.info("Example extension closed")

    # Event Handlers (automatically registered by decorators)

    @subscribe("hub.started")
    def on_hub_started(self, data):
        """Handle Hub started event."""
        self.logger.info("Hub has started - example extension responding")

    @subscribe("user.login")
    async def on_user_login(self, user_data):
        """Handle user login events."""
        self.logger.info(f"User logged in: {user_data}")

        # Example of emitting our own event
        if self.hub:
            await self.hub.emit(
                "example.user_welcomed",
                {"user": user_data, "message": "Welcome to Qi!"},
            )

    # Extension Points (provide functionality to other parts of the system)

    @extends("cli")
    def cli_commands(self):
        """Provide CLI commands for this extension."""
        return {
            "example": {
                "help": "Example commands",
                "commands": {
                    "hello": self.hello_command,
                    "status": self.status_command,
                },
            }
        }

    @extends("rest")
    def rest_routes(self):
        """Provide REST API routes for this extension."""
        return [
            {
                "path": "/api/example/hello",
                "method": "GET",
                "handler": self.hello_endpoint,
                "description": "Say hello",
            },
            {
                "path": "/api/example/status",
                "method": "GET",
                "handler": self.status_endpoint,
                "description": "Get extension status",
            },
        ]

    # Business Logic Methods

    def hello_command(self, args=None):
        """CLI command implementation."""
        self.logger.info("Hello from example extension CLI command!")
        return "Hello from Example Extension!"

    def status_command(self, args=None):
        """CLI status command implementation."""
        status = "initialized" if self._initialized else "not initialized"
        self.logger.info(f"Example extension status: {status}")
        return f"Example Extension Status: {status}"

    def hello_endpoint(self):
        """REST API endpoint implementation."""
        self.logger.info("Hello endpoint called")
        return {"message": "Hello from Example Extension API!"}

    def status_endpoint(self):
        """REST API status endpoint implementation."""
        return {
            "extension": "ExampleExtension",
            "initialized": self._initialized,
            "status": "running" if self._initialized else "stopped",
        }

    # Event handlers for application lifecycle

    def on_app_startup(self, data):
        """Handle application startup."""
        self.logger.info("Application is starting up")

    def on_app_shutdown(self, data):
        """Handle application shutdown."""
        self.logger.info("Application is shutting down")
