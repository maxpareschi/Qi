"""
Message bus handlers for the QiDbManager.

This module registers handlers for database-related messages on the hub.
"""

from typing import Any

from core.constants import HUB_ID
from core.db.adapters import AuthenticationError
from core.db.manager import qi_db_manager
from core.logger import get_logger
from core.messaging.hub import qi_hub

log = get_logger(__name__)


async def handle_auth_login(message: dict[str, Any]) -> dict[str, Any]:
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
        return await qi_db_manager.login(username, password)
    except Exception as e:
        log.error(f"Error during login: {e}")
        raise


async def handle_auth_validate(message: dict[str, Any]) -> dict[str, Any]:
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
        return await qi_db_manager.validate_token(token)
    except Exception as e:
        log.error(f"Error validating token: {e}")
        raise


async def handle_auth_logout(message: dict[str, Any]) -> dict[str, Any]:
    """
    Handle auth.logout messages.

    Args:
        message: The message payload (unused)

    Returns:
        Success status
    """
    qi_db_manager.logout()
    return {"success": True}


async def handle_db_project_list(message: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Handle db_service.project.list messages.

    Args:
        message: The message payload (unused)

    Returns:
        list of project dictionaries
    """
    try:
        return await qi_db_manager.list_projects()
    except Exception as e:
        log.error(f"Error listing projects: {e}")
        raise


async def handle_db_settings_get(message: dict[str, Any]) -> dict[str, Any]:
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
        return await qi_db_manager.get_settings(scope, addon)
    except Exception as e:
        log.error(f"Error getting settings: {e}")
        raise


async def handle_db_settings_save(message: dict[str, Any]) -> dict[str, Any]:
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
        await qi_db_manager.save_settings(scope, settings, addon)
        return {"success": True}
    except Exception as e:
        log.error(f"Error saving settings: {e}")
        raise


async def handle_db_bundle_list(message: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Handle db_service.bundle.list messages.

    Args:
        message: The message payload (unused)

    Returns:
        list of bundle dictionaries
    """
    try:
        return await qi_db_manager.list_bundles()
    except Exception as e:
        log.error(f"Error listing bundles: {e}")
        raise


async def handle_db_bundle_get(message: dict[str, Any]) -> dict[str, Any]:
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
        bundle = await qi_db_manager.get_bundle(name)
        if not bundle:
            raise ValueError(f"Bundle '{name}' not found")
        return bundle
    except Exception as e:
        log.error(f"Error getting bundle: {e}")
        raise


async def handle_db_bundle_active_get(message: dict[str, Any]) -> dict[str, Any]:
    """
    Handle db_service.bundle.active.get messages.

    Args:
        message: The message payload (unused)

    Returns:
        Active bundle name
    """
    try:
        active_bundle = await qi_db_manager.get_active_bundle()
        return {"active": active_bundle}
    except Exception as e:
        log.error(f"Error getting active bundle: {e}")
        raise


async def handle_db_bundle_active_set(message: dict[str, Any]) -> dict[str, Any]:
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
        await qi_db_manager.set_active_bundle(name)
        return {"success": True, "active": name}
    except Exception as e:
        log.error(f"Error setting active bundle: {e}")
        raise


def register_db_handlers() -> None:
    """
    Register all database-related handlers with the message bus.
    """
    # Authentication handlers
    qi_hub.on("auth.login", handle_auth_login, session_id=HUB_ID)
    qi_hub.on("auth.validate", handle_auth_validate, session_id=HUB_ID)
    qi_hub.on("auth.logout", handle_auth_logout, session_id=HUB_ID)

    # Project handlers
    qi_hub.on("db_service.project.list", handle_db_project_list, session_id=HUB_ID)

    # Settings handlers
    qi_hub.on("db_service.settings.get", handle_db_settings_get, session_id=HUB_ID)
    qi_hub.on("db_service.settings.save", handle_db_settings_save, session_id=HUB_ID)

    # Bundle handlers
    qi_hub.on("db_service.bundle.list", handle_db_bundle_list, session_id=HUB_ID)
    qi_hub.on("db_service.bundle.get", handle_db_bundle_get, session_id=HUB_ID)
    qi_hub.on(
        "db_service.bundle.active.get", handle_db_bundle_active_get, session_id=HUB_ID
    )
    qi_hub.on(
        "db_service.bundle.active.set", handle_db_bundle_active_set, session_id=HUB_ID
    )

    log.info("Database handlers registered with the message bus")
