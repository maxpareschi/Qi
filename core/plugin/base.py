# core/plugin/base.py

"""
This module contains the base class for all Qi plugins.
"""

import abc


class QiPluginBase(abc.ABC):
    """
    Abstract base class for all Qi plugins.  Provides:
      • Three abstract methods that every plugin must implement:
          - discover():   run at startup to discover resources or sub-plugins
          - register():   register handlers or connections into the bus/hub
          - process():    the main “work” method (may be async or sync)
    """

    def __init__(self) -> None:
        self._discover()
        self._register()

    def __repr__(self) -> str:
        return f"<QiPlugin(name={self.name!r})>"

    def _discover(self) -> None:
        # PluginBase pre-discover logic here
        self.discover()
        # PluginBase post-discover logic here

    def _register(self) -> None:
        # PluginBase pre-register logic here
        self.register()
        # PluginBase post-register logic here

    @abc.abstractmethod
    def discover(self) -> None:
        """
        Discover any resources, sub-plugins, file paths, etc., needed at startup.
        Called once (synchronously) by the hub before 'register()'.
        """

    @abc.abstractmethod
    def register(self) -> None:
        """
        Register this plugin's handlers, commands, or connections into the message bus/hub.
        Called once (synchronously) after 'discover()'.
        """

    @abc.abstractmethod
    async def process(self) -> None:
        """
        The main processing logic of this plugin.
        Called once (synchronously) after 'discover()'.
        """
