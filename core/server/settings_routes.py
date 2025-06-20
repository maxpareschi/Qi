# core/server/settings_routes.py

"""
This module contains the settings routes for the Qi server.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.logger import get_logger
from core.settings.manager import qi_settings_manager

log = get_logger(__name__)


class SettingsPatch(BaseModel):
    path: str = Field(..., description="Dot-separated path to the setting to update.")
    value: Any = Field(..., description="The new value for the setting.")


def create_settings_router() -> APIRouter:
    """Creates a FastAPI router for settings-related endpoints."""
    router = APIRouter(prefix="/settings", tags=["settings"])

    @router.get("/")
    async def get_all_settings() -> dict[str, Any]:
        """
        Retrieves the entire settings schema, including current values.
        """
        try:
            return qi_settings_manager.get_schema()
        except RuntimeError as e:
            log.error(f"Error getting settings schema: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.patch("/{scope}")
    async def patch_settings(scope: str, patch: SettingsPatch) -> dict[str, Any]:
        """
        Updates a setting value within a specific scope ('bundle', 'project', 'user').
        """
        if scope not in ("bundle", "project", "user"):
            raise HTTPException(
                status_code=400,
                detail="Invalid scope. Must be 'bundle', 'project', or 'user'.",
            )
        try:
            await qi_settings_manager.patch_value(scope, patch.path, patch.value)
            return {
                "status": "success",
                "message": f"Setting '{patch.path}' updated in scope '{scope}'.",
            }
        except (ValueError, NotImplementedError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            # This can happen if settings are not built, or other internal errors.
            log.error(f"Error patching setting: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
