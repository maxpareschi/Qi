# core_new/settings/bus_handlers.py
"""
This module contains the message handlers for the settings service.
"""

from core_new.di import container
from core_new.logger import get_logger
from core_new.messaging.hub import Hub
from core_new.models import QiMessage

log = get_logger(__name__)


class SettingsHandlerService:
    """Service class to encapsulate Settings message handling logic."""

    def __init__(self):
        self.settings_manager = container.get("settings_manager")
        self.hub: Hub = container.get("hub")

    async def handle_config_get(self, message: QiMessage) -> dict | None:
        """
        Handles requests to get a configuration value.
        """
        payload = message.payload
        path = payload.get("path")
        if not path:
            return None

        default = payload.get("default")
        value = self.settings_manager.get_value(path, default)
        return {"path": path, "value": value}

    async def handle_config_schema(self, message: QiMessage) -> dict:
        """
        Handles requests to get the configuration schema.
        """
        payload = message.payload
        path = payload.get("path")

        try:
            schema = self.settings_manager.get_schema(path)
            return {"schema": schema}
        except (RuntimeError, ValueError) as e:
            return {"error": str(e)}

    async def handle_config_patch(self, message: QiMessage) -> dict:
        """
        Handles requests to update a configuration value.
        """
        payload = message.payload
        scope = payload.get("scope")  # e.g., "user"
        path = payload.get("path")
        value = payload.get("value")

        if not all([scope, path]):
            return {"success": False, "error": "Scope and path are required."}

        try:
            await self.settings_manager.patch_value(scope, path, value)
            return {"success": True}
        except Exception as e:
            log.error(f"Error patching setting: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def register_handlers(self):
        """Registers all settings-related handlers with the message bus."""
        log.info("Registering settings message handlers...")
        self.hub.on("config.get")(self.handle_config_get)
        self.hub.on("config.schema")(self.handle_config_schema)
        self.hub.on("config.patch")(self.handle_config_patch)
        log.info("Settings message handlers registered.")


def register_settings_handlers():
    """Factory function to create and register Settings handlers."""
    service = SettingsHandlerService()
    service.register_handlers()
