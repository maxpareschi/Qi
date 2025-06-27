"""
Decorators module.

This module provides decorators for dependency injection, event handling, and extension points.
These decorators work with the Hub to provide a low-boilerplate, high-automation developer experience.
"""

from typing import Annotated, Any, Callable, TypeVar

from core.logger import get_logger

log = get_logger(__name__)

# Type variable for preserving decorator type information
F = TypeVar("F", bound=Callable[..., Any])


class Injectable:
    """
    Marker class for dependency injection.

    Use this to mark class attributes that should be injected by the Hub.

    Usage:
        class MyService:
            config: Injectable[QiLaunchConfig]
            hub: Injectable[Hub]
            optional_service: Injectable[SomeService] = None  # Optional dependency

            # Non-injectable attribute
            my_data: dict = {}
    """

    def __class_getitem__(cls, item):
        """Support Injectable[Type] syntax."""
        return Annotated[item, cls]


def inject(*dependencies: str) -> Callable[[type], type]:
    """
    Mark a class for automatic dependency injection.

    Three usage modes:
    1. Explicit dependencies: @inject("config", "hub", "bus")
    2. Auto-scan mode: @inject() - scans all class annotations for service names
    3. Injectable markers: Use Injectable[Type] annotations (no decorator args needed)

    Args:
        *dependencies: Optional explicit service names to inject

    Usage:
        # Mode 1: Explicit dependencies
        @inject("config", "hub", "bus")
        class MyService:
            config: QiLaunchConfig
            hub: Hub
            bus: EventBus

        # Mode 2: Auto-scan all annotations
        @inject()
        class MyService:
            config: QiLaunchConfig  # Auto-injected based on attribute name
            hub: Hub               # Auto-injected based on attribute name
            my_data: dict = {}     # Not injected (no service named 'my_data')

        # Mode 3: Injectable markers (cleanest)
        class MyService:
            config: Injectable[QiLaunchConfig]  # Injected
            hub: Injectable[Hub]                # Injected
            my_data: dict = {}                  # Not injected

    Note:
        - Injectable markers don't require @inject decorator
        - Auto-scan mode tries to inject all annotated attributes
        - Missing dependencies will log warnings but not fail
    """

    def decorator(cls: type) -> type:
        if dependencies:
            # Mode 1: Explicit mode - use provided dependency names
            cls.__qi_inject__ = dependencies
            log.debug(f"Marked {cls.__name__} for explicit injection: {dependencies}")
        else:
            # Mode 2: Auto-scan mode - extract from class annotations
            if hasattr(cls, "__annotations__"):
                # Get all annotated attributes as potential dependencies
                injectable_attrs = list(cls.__annotations__.keys())
                cls.__qi_inject__ = tuple(injectable_attrs)
                log.debug(
                    f"Marked {cls.__name__} for auto-scan injection: {injectable_attrs}"
                )
            else:
                cls.__qi_inject__ = ()
                log.debug(
                    f"Marked {cls.__name__} for injection but no annotations found"
                )

        return cls

    # Check if class has Injectable markers (Mode 3)
    def check_injectable_markers(cls: type) -> type:
        if hasattr(cls, "__annotations__"):
            injectable_attrs = []
            for attr_name, annotation in cls.__annotations__.items():
                # Check if annotation uses Injectable marker
                if hasattr(annotation, "__origin__") and hasattr(
                    annotation, "__metadata__"
                ):
                    # This is an Annotated type, check metadata
                    if any(
                        isinstance(meta, type) and issubclass(meta, Injectable)
                        for meta in annotation.__metadata__
                    ):
                        injectable_attrs.append(attr_name)
                elif (
                    hasattr(annotation, "__origin__")
                    and annotation.__origin__ is Injectable
                ):
                    # Direct Injectable[Type] usage
                    injectable_attrs.append(attr_name)

            if injectable_attrs:
                cls.__qi_inject__ = tuple(injectable_attrs)
                log.debug(
                    f"Found Injectable markers in {cls.__name__}: {injectable_attrs}"
                )

        return cls

    # If no dependencies specified, this could be auto-scan or the decorator might not be used
    if not dependencies:
        return decorator
    else:
        return decorator


# Auto-detect Injectable markers without requiring @inject decorator
def __init_subclass_hook__(cls):
    """Automatically detect Injectable markers in classes."""
    original_init_subclass = cls.__init_subclass__

    @classmethod
    def new_init_subclass(cls, **kwargs):
        # Check for Injectable markers
        if hasattr(cls, "__annotations__"):
            injectable_attrs = []
            for attr_name, annotation in cls.__annotations__.items():
                # Check if annotation uses Injectable marker
                if (
                    hasattr(annotation, "__origin__")
                    and getattr(annotation, "__origin__", None) is Injectable
                ):
                    injectable_attrs.append(attr_name)

            if injectable_attrs:
                cls.__qi_inject__ = tuple(injectable_attrs)
                log.debug(
                    f"Auto-detected Injectable markers in {cls.__name__}: {injectable_attrs}"
                )

        original_init_subclass(**kwargs)

    cls.__init_subclass__ = new_init_subclass
    return cls


def subscribe(event: str) -> Callable[[F], F]:
    """
    Mark a method as a message handler for a specific topic.

    The EventBus will automatically register this method to handle messages with the specified topic.
    Methods can be sync or async and receive QiMessage objects.

    Args:
        event: The topic/event name to subscribe to

    Usage:
        class MyExtension(QiExtensionBase):
            @subscribe("app.started")
            def on_app_start(self, message: QiMessage):
                print(f"App started! Payload: {message.payload}")

            @subscribe("user.login")
            async def on_user_login(self, message: QiMessage):
                await self.log_user_activity(message.payload)

    Note:
        - Handlers receive QiMessage objects with full envelope information
        - Handlers are registered automatically when extension is registered with Hub
        - Sync handlers are executed in thread pool to avoid blocking
        - The Hub coordinates registration, but EventBus handles routing
    """

    def decorator(func: F) -> F:
        func.__qi_subscribe__ = event
        log.debug(f"Marked {func.__name__} as handler for topic: {event}")
        return func

    return decorator


def extends(domain: str) -> Callable[[F], F]:
    """
    Mark a method as providing extensions for a specific domain.

    The method should return a list of items (commands, routes, etc.) that extend
    the specified domain (cli, rest, gui, etc.).

    Args:
        domain: The domain to extend (e.g., "cli", "rest", "gui")

    Usage:
        class MyExtension(QiExtensionBase):
            @extends("cli")
            def cli_commands(self):
                return [MyCommand(), AnotherCommand()]

            @extends("rest")
            def rest_routes(self):
                return [my_router]

            @extends("gui")
            def gui_components(self):
                return [{"name": "my_widget", "component": MyWidget}]

    Note:
        - Methods are called during extension registration
        - Return value should be a list of extension items
        - Different domains may expect different item formats
    """

    def decorator(func: F) -> F:
        func.__qi_extends__ = domain
        log.debug(f"Marked {func.__name__} as extending domain: {domain}")
        return func

    return decorator


def lifecycle(phase: str) -> Callable[[F], F]:
    """
    Mark a method to be called during a specific lifecycle phase.

    This is a convenience decorator that subscribes to standard lifecycle events.

    Args:
        phase: The lifecycle phase ("discover", "register", "initialize", "start", "shutdown")

    Usage:
        class MyExtension(QiExtensionBase):
            @lifecycle("initialize")
            def setup_database(self, data):
                self.db = create_database_connection()

            @lifecycle("shutdown")
            def cleanup(self, data):
                self.db.close()

    Note:
        - This is syntactic sugar for @subscribe(f"extension.{phase}")
        - Standard phases are emitted by the extension loading system
        - Custom phases can be defined and emitted as needed
    """

    def decorator(func: F) -> F:
        event = f"extension.{phase}"
        func.__qi_subscribe__ = event
        log.debug(f"Marked {func.__name__} for lifecycle phase: {phase}")
        return func

    return decorator


def singleton(cls: type) -> type:
    """
    Mark a class as a singleton within the Hub's service registry.

    This decorator ensures that only one instance of the class exists
    per Hub instance. Subsequent requests for the service will return
    the same instance.

    Args:
        cls: The class to make singleton

    Usage:
        @singleton
        @inject("config")
        class DatabaseManager:
            def __init__(self):
                # Dependencies auto-injected by @inject decorator
                self.connection = None

    Note:
        - The Hub enforces singleton behavior during service registration
        - This is primarily documentary - the Hub naturally creates singletons
        - Can be combined with other decorators
    """
    cls.__qi_singleton__ = True
    log.debug(f"Marked {cls.__name__} as singleton")
    return cls


def service(name: str | None = None) -> Callable[[type], type]:
    """
    Mark a class as a service with an optional custom name.

    This decorator can be used to specify a custom service name for registration
    instead of using the class name.

    Args:
        name: Custom service name (defaults to class name)

    Usage:
        @service("db")
        class DatabaseManager:
            pass

        @service()  # Uses class name
        class LoggerService:
            pass

    Note:
        - If no name provided, class name is used
        - Custom names can help with service lookup clarity
        - This is primarily documentary - registration name is set during hub.register()
    """

    def decorator(cls: type) -> type:
        service_name = name if name is not None else cls.__name__
        cls.__qi_service_name__ = service_name
        log.debug(f"Marked {cls.__name__} as service: {service_name}")
        return cls

    return decorator


# Convenience functions for common patterns


def on(event: str) -> Callable[[F], F]:
    """
    Alias for @subscribe decorator for clarity.

    Args:
        event: The event name to handle

    Usage:
        @on("user.created")
        def handle_user_creation(self, user_data):
            # Handle user creation
            pass
    """
    return subscribe(event)


def cli_extension(func: F) -> F:
    """
    Convenience decorator for CLI extensions.

    Usage:
        @cli_extension
        def my_commands(self):
            return [MyCommand()]
    """
    return extends("cli")(func)


def rest_extension(func: F) -> F:
    """
    Convenience decorator for REST API extensions.

    Usage:
        @rest_extension
        def my_routes(self):
            return [my_router]
    """
    return extends("rest")(func)


def gui_extension(func: F) -> F:
    """
    Convenience decorator for GUI extensions.

    Usage:
        @gui_extension
        def my_components(self):
            return [MyWidget()]
    """
    return extends("gui")(func)
