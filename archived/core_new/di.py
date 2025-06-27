"""
Dependency Injection Container for Qi.

This module provides a simple dependency injection container that allows
components to declare their dependencies explicitly, making the system
more testable and the dependencies more visible.
"""

from typing import Any, Callable, Dict, Type, TypeVar, cast

T = TypeVar("T")


class ServiceContainer:
    """
    A simple dependency injection container.

    This container manages service instances and factories, allowing for
    lazy initialization and explicit dependency declaration.
    """

    def __init__(self):
        self._instances: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._resolving: set[str] = set()  # Track services currently being resolved

    def register_instance(self, name: str, instance: Any) -> None:
        """Register an existing instance under the given name."""
        self._instances[name] = instance

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """Register a factory function that will create the service on demand."""
        self._factories[name] = factory

    def register_singleton(self, name: str, factory: Callable[[], Any]) -> None:
        """
        Register a factory function that will be called once to create a singleton.

        The factory will be called the first time the service is requested,
        and the same instance will be returned for subsequent requests.
        """

        def singleton_factory() -> Any:
            if name not in self._instances:
                self._instances[name] = factory()
            return self._instances[name]

        self._factories[name] = singleton_factory

    def get(self, name: str) -> Any:
        """
        Get a service by name.

        If the service is already instantiated, returns the instance.
        If not, calls the factory function to create it.

        Args:
            name: The name of the service to get.

        Returns:
            The service instance.

        Raises:
            KeyError: If the service is not registered.
            RuntimeError: If a circular dependency is detected.
        """
        if name in self._instances:
            return self._instances[name]

        if name in self._factories:
            # Check for circular dependency
            if name in self._resolving:
                raise RuntimeError(f"Circular dependency detected for service '{name}'")

            self._resolving.add(name)
            try:
                return self._factories[name]()
            finally:
                self._resolving.discard(name)

        raise KeyError(f"Service '{name}' not registered")

    def get_typed(self, name: str, expected_type: Type[T]) -> T:
        """
        Get a service by name and cast it to the expected type.

        This is a convenience method for type-safe access to services.

        Args:
            name: The name of the service to get.
            expected_type: The expected type of the service.

        Returns:
            The service instance, cast to the expected type.

        Raises:
            KeyError: If the service is not registered.
            TypeError: If the service is not of the expected type.
        """
        service = self.get(name)
        if not isinstance(service, expected_type):
            raise TypeError(
                f"Service '{name}' is of type {type(service)}, not {expected_type}"
            )
        return cast(T, service)

    def has(self, name: str) -> bool:
        """
        Check if a service is registered.

        Args:
            name: The name of the service to check.

        Returns:
            True if the service is registered, False otherwise.
        """
        return name in self._instances or name in self._factories

    def clear(self) -> None:
        """Clear all registered services and factories."""
        self._instances.clear()
        self._factories.clear()


# Create a global container instance
container = ServiceContainer()
