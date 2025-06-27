"""
Abstract Base Classes for Qi.

This module contains common abstract base classes used throughout the
core application to enforce consistent interfaces.
"""

import abc


class ManagerBase(abc.ABC):
    """
    Abstract base class for all manager services in Qi.

    This class defines a common lifecycle interface that all managers should
    adhere to, ensuring consistent initialization, startup, and shutdown
    procedures across the application. This makes the application's main
    orchestration logic simpler and more reliable.
    """

    @abc.abstractmethod
    async def initialize(self) -> None:
        """
        Perform initial setup for the manager.

        This method is called once during application startup before any
        services are started. It's the place for one-time setup tasks,
        like registering handlers or loading initial data, but not for
        starting long-running processes.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def start(self) -> None:
        """
        Start any long-running processes or services managed by this class.

        This method is called after all managers have been initialized.
        It's intended for starting background tasks, servers, or event loops.
        If a manager does not have a long-running process, this method
        can be a no-op (e.g., `pass`).
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def shutdown(self) -> None:
        """
        Gracefully stop all services and perform cleanup.

        This method is called during application shutdown. It should release
        resources, close connections, and stop any background tasks that were
        started in the `start` method.
        """
        raise NotImplementedError
