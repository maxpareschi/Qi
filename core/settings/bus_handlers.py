from core.constants import HUB_ID
from core.logger import get_logger
from core.messaging.hub import qi_hub
from core.settings.manager import QiSettingsManager

log = get_logger(__name__)


def register_settings_handlers(settings_manager: QiSettingsManager) -> None:
    """
    Register all settings-related handlers with the message bus.
    """

    @qi_hub.on("config.get", session_id=HUB_ID)
    async def handle_config_get(message: dict) -> dict | None:
        """
        Handles requests to get a configuration value.

        Payload:
            path (str): The dot-separated path to the setting.
            default (any, optional): A default value to return if the path
                                     is not found.
        """
        payload = message.get("payload", {})
        path = payload.get("path")
        if not path:
            return None

        default = payload.get("default")
        value = settings_manager.get_value(path, default)
        return {"path": path, "value": value}

    @qi_hub.on("config.schema", session_id=HUB_ID)
    async def handle_config_schema(message: dict) -> dict:
        """
        Handles requests to get the configuration schema.

        Payload:
            path (str, optional): The dot-separated path to get a specific part of the schema.
                                 If not provided, returns the full schema.

        Returns:
            The JSON schema for the requested configuration section
        """
        payload = message.get("payload", {})
        path = payload.get("path")

        try:
            schema = settings_manager.get_schema(path)
            if path:
                return {"path": path, "schema": schema}
            else:
                return {"schema": schema}
        except RuntimeError:
            return {"error": "Settings have not been built yet"}
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            log.error(f"Error retrieving schema: {e}")
            return {"error": str(e)}

    @qi_hub.on("config.patch", session_id=HUB_ID)
    async def handle_config_patch(message: dict) -> dict:
        """
        Handles requests to update a configuration value.
        """
        payload = message.get("payload", {})
        scope = payload.get("scope")  # e.g., "user"
        path = payload.get("path")
        value = payload.get("value")

        if not all([scope, path]):
            return {"success": False, "error": "Scope and path are required."}

        try:
            await settings_manager.patch_value(scope, path, value)
            return {"success": True}
        except Exception as e:
            log.error(f"Error patching setting: {e}")
            return {"success": False, "error": str(e)}

    log.info("Settings handlers registered with the message bus.")
