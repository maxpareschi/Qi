"""
Message bus handlers for the QiDbManager.

This module registers handlers for database-related messages on the hub.
"""

from typing import Any

from core.constants import HUB_ID
from core.db.adapters import AuthenticationError
from core.db.manager import QiDbManager
from core.logger import get_logger
from core.messaging.hub import qi_hub

log = get_logger(__name__)


class _DbHandlerService:
    def __init__(self, db_manager: QiDbManager):
        self.db_manager = db_manager

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

    async def handle_db_settings_get(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Handle db_service.settings.get messages.

        Args:
            message: The message payload containing:
                - scope: The settings scope ('bundle', 'project', 'user')
                - addon: Optional addon name to filter by

        Returns:
            dictionary of settings
        """
        payload = message.get("payload", {})
        scope = payload.get("scope")
        addon = payload.get("addon")

        if not scope:
            raise ValueError("Settings scope is required")

        try:
            return await self.db_manager.get_settings(scope, addon)
        except Exception as e:
            log.error(f"Error getting settings: {e}")
            raise

    async def handle_db_settings_save(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Handle db_service.settings.save messages.

        Args:
            message: The message payload containing:
                - scope: The settings scope ('bundle', 'project', 'user')
                - settings: dictionary of settings to save
                - addon: Optional addon name to filter by

        Returns:
            Success status
        """
        payload = message.get("payload", {})
        scope = payload.get("scope")
        settings = payload.get("settings", {})
        addon = payload.get("addon")

        if not scope:
            raise ValueError("Settings scope is required")

        try:
            await self.db_manager.save_settings(scope, settings, addon)
            return {"success": True}
        except Exception as e:
            log.error(f"Error saving settings: {e}")
            raise

    async def handle_db_bundle_list(
        self, message: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Handle db_service.bundle.list messages.

        Args:
            message: The message payload (unused)

        Returns:
            list of bundle dictionaries
        """
        try:
            return await self.db_manager.list_bundles()
        except Exception as e:
            log.error(f"Error listing bundles: {e}")
            raise

    async def handle_db_bundle_get(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Handle db_service.bundle.get messages.

        Args:
            message: The message payload containing:
                - name: The name of the bundle

        Returns:
            Bundle information
        """
        payload = message.get("payload", {})
        name = payload.get("name")

        if not name:
            raise ValueError("Bundle name is required")

        try:
            bundle = await self.db_manager.get_bundle(name)
            if not bundle:
                raise ValueError(f"Bundle '{name}' not found")
            return bundle
        except Exception as e:
            log.error(f"Error getting bundle: {e}")
            raise

    async def handle_db_bundle_active_get(
        self, message: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Handle db_service.bundle.active.get messages.

        Args:
            message: The message payload (unused)

        Returns:
            Active bundle name
        """
        try:
            active_bundle = await self.db_manager.get_active_bundle()
            return {"active": active_bundle}
        except Exception as e:
            log.error(f"Error getting active bundle: {e}")
            raise

    async def handle_db_bundle_active_set(
        self, message: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Handle db_service.bundle.active.set messages.

        Args:
            message: The message payload containing:
                - name: The name of the bundle to activate

        Returns:
            Success status
        """
        payload = message.get("payload", {})
        name = payload.get("name")

        if not name:
            raise ValueError("Bundle name is required")

        try:
            await self.db_manager.set_active_bundle(name)
            return {"success": True, "active": name}
        except Exception as e:
            log.error(f"Error setting active bundle: {e}")
            raise


def register_db_handlers(db_manager: QiDbManager) -> None:
    """
    Register all database-related handlers with the message bus.
    """
    handler_service = _DbHandlerService(db_manager)

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

    # Settings handlers
    qi_hub.on(
        "db_service.settings.get",
        handler_service.handle_db_settings_get,
        session_id=HUB_ID,
    )
    qi_hub.on(
        "db_service.settings.save",
        handler_service.handle_db_settings_save,
        session_id=HUB_ID,
    )

    # Bundle handlers
    qi_hub.on(
        "db_service.bundle.list",
        handler_service.handle_db_bundle_list,
        session_id=HUB_ID,
    )
    qi_hub.on(
        "db_service.bundle.get",
        handler_service.handle_db_bundle_get,
        session_id=HUB_ID,
    )
    qi_hub.on(
        "db_service.bundle.active.get",
        handler_service.handle_db_bundle_active_get,
        session_id=HUB_ID,
    )
    qi_hub.on(
        "db_service.bundle.active.set",
        handler_service.handle_db_bundle_active_set,
        session_id=HUB_ID,
    )

    # Low-level data handlers
    # (These might be added in the future if direct data access is needed)
    # qi_hub.on("db_service.data.get", handle_db_data_get, session_id=HUB_ID)
    # qi_hub.on("db_service.data.save", handle_db_data_save, session_id=HUB_ID)
    # qi_hub.on("db_service.data.delete", handle_db_data_delete, session_id=HUB_ID)

    log.info("Database message handlers registered")
