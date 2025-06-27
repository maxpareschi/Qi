"""
This module contains the message handlers for the database service.
"""

from typing import Any

from core_new.db.adapters import AuthenticationError
from core_new.di import container
from core_new.logger import get_logger
from core_new.messaging.hub import Hub
from core_new.models import QiMessage

log = get_logger(__name__)


class DbHandlerService:
    """Service class to encapsulate DB message handling logic."""

    def __init__(self):
        self.db_manager = container.get("db_manager")
        self.hub: Hub = container.get("hub")

    async def handle_auth_login(self, message: QiMessage) -> dict[str, Any]:
        """Handles auth.login messages."""
        payload = message.payload
        username = payload.get("username")
        password = payload.get("password")

        if not username or not password:
            log.warning("Login attempt with missing credentials")
            raise AuthenticationError("Username and password are required")

        return await self.db_manager.login(username, password)

    async def handle_auth_validate(self, message: QiMessage) -> dict[str, Any]:
        """Handles auth.validate messages."""
        payload = message.payload
        token = payload.get("token")
        return await self.db_manager.validate_token(token)

    async def handle_auth_logout(self, message: QiMessage) -> dict[str, Any]:
        """Handles auth.logout messages."""
        # The logout method doesn't take any parameters
        await self.db_manager.logout()
        return {"success": True}

    async def handle_db_project_list(self, message: QiMessage) -> list[dict[str, Any]]:
        """Handles db.project.list messages."""
        return await self.db_manager.list_projects()

    async def handle_db_get_settings(self, message: QiMessage) -> dict[str, Any]:
        """Handles db.settings.get messages."""
        payload = message.payload
        scope = payload.get("scope")
        if not scope:
            return {"error": "Scope is required"}
        return await self.db_manager.get_settings(scope)

    async def handle_db_save_settings(self, message: QiMessage) -> dict[str, Any]:
        """Handles db.settings.save messages."""
        payload = message.payload
        scope = payload.get("scope")
        settings = payload.get("settings")
        if not scope or not settings:
            return {"error": "Scope and settings are required"}
        await self.db_manager.save_settings(scope, settings)
        return {"success": True}

    def register_handlers(self):
        """Registers all DB-related handlers with the message bus."""
        log.info("Registering database message handlers...")
        self.hub.on("auth.login")(self.handle_auth_login)
        self.hub.on("auth.validate")(self.handle_auth_validate)
        self.hub.on("auth.logout")(self.handle_auth_logout)
        self.hub.on("db.project.list")(self.handle_db_project_list)
        self.hub.on("db.settings.get")(self.handle_db_get_settings)
        self.hub.on("db.settings.save")(self.handle_db_save_settings)
        log.info("Database message handlers registered.")


def register_db_handlers():
    """Factory function to create and register DB handlers."""
    service = DbHandlerService()
    service.register_handlers()
