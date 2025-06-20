# core/db/bus_handlers.py

"""
This module contains the message handlers for the database service.
"""

from typing import Any

from core.constants import HUB_ID
from core.db.adapters import AuthenticationError
from core.db.manager import qi_db_manager
from core.logger import get_logger
from core.messaging.hub import qi_hub

log = get_logger(__name__)


class _DbHandlerService:
    def __init__(self):
        self.db_manager = qi_db_manager

    async def handle_auth_login(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Handle auth.login messages.

        Args:
            message: The message payload containing:
                - username: The user's login name
                - password: The user's password

        Returns:
            User information and token
        """
        payload = message.get("payload", {})
        username = payload.get("username")
        password = payload.get("password")

        if not username or not password:
            log.warning("Login attempt with missing credentials")
            raise AuthenticationError("Username and password are required")

        try:
            return await self.db_manager.login(username, password)
        except Exception as e:
            log.error(f"Error during login: {e}")
            raise

    async def handle_auth_validate(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Handle auth.validate messages.

        Args:
            message: The message payload containing:
                - token: Optional token to validate (uses current if not provided)

        Returns:
            User information if token is valid
        """
        payload = message.get("payload", {})
        token = payload.get("token")

        try:
            return await self.db_manager.validate_token(token)
        except Exception as e:
            log.error(f"Error validating token: {e}")
            raise

    async def handle_auth_logout(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Handle auth.logout messages.

        Args:
            message: The message payload (unused)

        Returns:
            Success status
        """
        self.db_manager.logout()
        return {"success": True}

    async def handle_db_project_list(
        self, message: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Handle db_service.project.list messages.

        Args:
            message: The message payload (unused)

        Returns:
            list of project dictionaries
        """
        try:
            return await self.db_manager.list_projects()
        except Exception as e:
            log.error(f"Error listing projects: {e}")
            raise


def register_db_handlers() -> None:
    """
    Register all database-related handlers with the message bus.
    """
    handler_service = _DbHandlerService()

    # Authentication handlers
    qi_hub.on("auth.login", handler_service.handle_auth_login, session_id=HUB_ID)
    qi_hub.on("auth.validate", handler_service.handle_auth_validate, session_id=HUB_ID)
    qi_hub.on("auth.logout", handler_service.handle_auth_logout, session_id=HUB_ID)

    # Project handlers
    qi_hub.on(
        "db_service.project.list",
        handler_service.handle_db_project_list,
        session_id=HUB_ID,
    )

    # NOTE: Settings and Bundle handlers are intentionally removed.
    # All settings and bundle operations should go through the high-level
    # QiSettingsManager and QiBundleManager, which are exposed via
    # `config.*` messages and REST endpoints. This prevents state
    # inconsistencies that would arise from modifying the database directly
    # without triggering the necessary application-level logic (e.g.,
    # settings model rebuilds).

    # Low-level data handlers
    # (These might be added in the future if direct data access is needed)
    # qi_hub.on("db_service.data.get", handle_db_data_get, session_id=HUB_ID)
    # qi_hub.on("db_service.data.save", handle_db_data_save, session_id=HUB_ID)
    # qi_hub.on("db_service.data.delete", handle_db_data_delete, session_id=HUB_ID)

    log.info("Database message handlers registered")
