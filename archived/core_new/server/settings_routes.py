"""
Settings Routes for Qi.

This module provides FastAPI routes for settings management.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core_new.di import container
from core_new.logger import get_logger

log = get_logger("server.settings_routes")


class SettingsPatch(BaseModel):
    """Model for patching a setting value."""

    path: str = Field(..., description="Dot-separated path to the setting to update.")
    value: Any = Field(..., description="The new value for the setting.")


def create_settings_router() -> APIRouter:
    """
    Creates a FastAPI router for settings-related endpoints.

    Returns:
        A FastAPI router with settings management endpoints.
    """
    router = APIRouter(prefix="/settings", tags=["settings"])

    @router.get("/")
    async def get_all_settings() -> dict[str, Any]:
        """
        Retrieves the entire settings schema, including current values.
        """
        settings_manager = container.get("settings_manager")
        try:
            return settings_manager.get_schema()
        except RuntimeError as e:
            log.error(f"Error getting settings schema: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.patch("/{scope}")
    async def patch_settings(scope: str, patch: SettingsPatch) -> dict[str, Any]:
        """
        Updates a setting value within a specific scope ('bundle', 'project', 'user').

        Args:
            scope: The settings scope ('bundle', 'project', or 'user')
            patch: The setting path and new value

        Returns:
            A success message

        Raises:
            HTTPException: If the scope is invalid or the setting cannot be updated
        """
        if scope not in ("bundle", "project", "user"):
            raise HTTPException(
                status_code=400,
                detail="Invalid scope. Must be 'bundle', 'project', or 'user'.",
            )

        settings_manager = container.get("settings_manager")
        try:
            await settings_manager.patch_value(scope, patch.path, patch.value)
            return {
                "status": "success",
                "message": f"Setting '{patch.path}' updated in scope '{scope}'.",
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except NotImplementedError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            # This can happen if settings are not built, or other internal errors.
            log.error(f"Error patching setting: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
