# core/hub.py

"""
Hub module.

This module provides the central Hub class that coordinates services and manages dependencies.
The Hub is purely a service orchestrator - event handling is done by the MessageBus service.
"""

import asyncio
from typing import Any

from core.config import QiLaunchConfig
from core.logger import get_logger

log = get_logger(__name__)


class Hub:
    """
    Central service coordinator and dependency injection container.

    The Hub is responsible ONLY for:
    - Service registration and discovery
    - Automatic dependency injection via decorators
    - Extension lifecycle management

    Events and messaging are handled by the MessageBus service.
    """

    def __init__(self, launch_config: QiLaunchConfig):
        """
        Initialize the Hub with launch configuration.

        Args:
            launch_config: The QiLaunchConfig instance containing startup settings
        """
        self.config = launch_config
        self.services: dict[str, Any] = {}
        self.extensions: list[Any] = []  # Will hold QiExtensionBase instances
        self._lock = asyncio.Lock()

        # Register the config and hub itself as services
        self.services["config"] = launch_config
        self.services["hub"] = self

        log.info("Hub initialized")

    def register(self, name: str, service: Any) -> None:
        """
        Register a service with the Hub.

        This method:
        1. Stores the service in the registry
        2. Auto-injects hub reference if service has 'hub' attribute
        3. Wires dependencies based on decorators
        4. Registers any decorated handlers with MessageBus

        Args:
            name: Unique identifier for the service
            service: The service instance to register
        """
        self.services[name] = service

        # Auto-inject hub reference if service expects it
        if hasattr(service, "hub"):
            service.hub = self

        # Auto-wire dependencies based on decorators
        self._wire_dependencies(service)

        # Auto-register decorated handlers for any service (not just extensions)
        self._register_service_handlers(service)

        log.debug(f"Registered service: {name}")

    def get(self, name: str) -> Any:
        """
        Retrieve a service by name.

        Args:
            name: The service identifier

        Returns:
            The requested service instance

        Raises:
            KeyError: If the service is not registered
        """
        if name not in self.services:
            raise KeyError(
                f"Service '{name}' not found. Available services: {list(self.services.keys())}"
            )
        return self.services[name]

    def has_service(self, name: str) -> bool:
        """
        Check if a service is registered.

        Args:
            name: The service identifier

        Returns:
            True if service exists, False otherwise
        """
        return name in self.services

    def _wire_dependencies(self, service: Any) -> None:
        """
        Auto-wire dependencies for a service based on decorators.

        This method looks for the __qi_inject__ attribute set by @inject decorator
        and injects the requested dependencies.

        Args:
            service: The service instance to wire dependencies for
        """
        if not hasattr(service, "__qi_inject__"):
            return

        dependencies = getattr(service, "__qi_inject__")
        for dep_name in dependencies:
            if dep_name in self.services:
                setattr(service, dep_name, self.services[dep_name])
                log.debug(f"Injected {dep_name} into {service.__class__.__name__}")
            else:
                log.warning(
                    f"Dependency '{dep_name}' not available for {service.__class__.__name__}"
                )

    def register_extension(self, extension: Any) -> None:
        """
        Register an extension with the Hub.

        This method:
        1. Adds extension to the extensions list
        2. Registers it as a service
        3. Auto-wires its dependencies
        4. Registers any decorated event handlers with MessageBus

        Args:
            extension: The extension instance (should inherit from QiExtensionBase)
        """
        self.extensions.append(extension)

        # Register as a service using class name
        service_name = extension.__class__.__name__
        self.register(service_name, extension)

        log.info(f"Registered extension: {service_name}")

    def _register_extension_handlers(self, extension: Any) -> None:
        """
        DEPRECATED: Use _register_service_handlers instead.

        This method is kept for compatibility but redirects to the unified handler registration.
        """
        self._register_service_handlers(extension)

    def _register_service_handlers(self, service: Any) -> None:
        """
        Scan any service for decorated methods and register them with EventBus.

        Looks for methods with __qi_subscribe__ attribute set by @subscribe decorator.

        Args:
            service: The service instance to scan
        """
        if not self.has_service("bus"):
            # EventBus not available yet, skip for now
            return

        event_bus = self.get("bus")

        for name in dir(service):
            if name.startswith("_"):
                continue

            attr = getattr(service, name)
            if callable(attr) and hasattr(attr, "__qi_subscribe__"):
                topic = attr.__qi_subscribe__
                event_bus.register_handler(topic, attr)
                log.debug(
                    f"Auto-registered {service.__class__.__name__}.{name} for topic '{topic}'"
                )

    def setup_core_services(self) -> None:
        """Set up core services (EventBus, ExtensionManager, Server)."""
        from core.bus import EventBus
        from core.extension import ExtensionManager
        from core.server import ServerManager

        # Register EventBus first
        event_bus = EventBus()
        self.register("bus", event_bus)

        # Register ExtensionManager
        extension_manager = ExtensionManager(self, self.config)
        self.register("extension_manager", extension_manager)

        # Register ServerManager
        server = ServerManager()
        self.register("server", server)

        # Re-register handlers for services that were registered before EventBus
        self._register_pending_handlers()

        log.info("Core services registered")

    def _register_pending_handlers(self) -> None:
        """Register handlers for services that were registered before EventBus was available."""
        if not self.has_service("bus"):
            return

        event_bus = self.get("bus")

        # Go through all services and register any handlers that weren't registered yet
        for service_name, service in self.services.items():
            if service_name in ("bus", "config", "hub"):
                continue  # Skip core services

            # Register handlers for this service
            for name in dir(service):
                if name.startswith("_"):
                    continue

                attr = getattr(service, name)
                if callable(attr) and hasattr(attr, "__qi_subscribe__"):
                    topic = attr.__qi_subscribe__

                    # Check if handler is already registered
                    existing_handlers = event_bus.handlers.get(topic, [])
                    if attr not in existing_handlers:
                        event_bus.register_handler(topic, attr)
                        log.debug(
                            f"Registered pending handler {service.__class__.__name__}.{name} for topic '{topic}'"
                        )

    async def discover_extensions(self) -> None:
        """Discover and load extensions from configured paths."""
        extension_manager = self.get("extension_manager")
        await extension_manager.discover_and_load_extensions()

    async def initialize_extensions(self) -> None:
        """Initialize all loaded extensions."""
        extension_manager = self.get("extension_manager")
        await extension_manager.initialize_extensions()

    async def start_extensions(self) -> None:
        """Start all extensions (runs after initialization)."""
        extension_manager = self.get("extension_manager")
        await extension_manager.start_extensions()

    async def start(self) -> None:
        """Start the Hub and all its services."""
        # Start EventBus
        if self.has_service("bus"):
            event_bus = self.get("bus")
            # EventBus doesn't need explicit start, it's connection-driven

        # Start Server
        if self.has_service("server"):
            server = self.get("server")
            await server.start()

        log.info("Hub started")

    async def shutdown(self) -> None:
        """Shutdown the Hub and all services gracefully."""
        # Shutdown extension manager if it exists
        if self.has_service("extension_manager"):
            extension_manager = self.get("extension_manager")
            await extension_manager.shutdown_extensions()

        # Shutdown server
        if self.has_service("server"):
            server = self.get("server")
            await server.shutdown()

        # Clear all services
        self.services.clear()

        log.info("Hub shutdown complete")

    def list_services(self) -> list[str]:
        """
        List all registered service names.

        Returns:
            List of service names
        """
        return list(self.services.keys())

    def list_extensions(self) -> list[str]:
        """
        List all loaded extension names.

        Returns:
            List of extension names
        """
        if self.has_service("extension_manager"):
            extension_manager = self.get("extension_manager")
            return extension_manager.list_extensions()
        return []
