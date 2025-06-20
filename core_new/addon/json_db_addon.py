"""
Qi addon to provide a JSON file-based database service for the new core.
"""

from pathlib import Path

from core_new.addon.base import AddonRole, QiAddonBase
from core_new.config import app_config
from core_new.db.file_db import JsonFileDbAdapter
from core_new.logger import get_logger

log = get_logger("addon.json_db")


class NewJsonFileDbAddon(QiAddonBase):
    """A provider addon that supplies the JsonFileDbAdapter."""

    def __init__(self):
        data_dir = Path(app_config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        self._adapter = JsonFileDbAdapter(str(data_dir))

    @property
    def name(self) -> str:
        return "core_json_db"

    @property
    def role(self) -> AddonRole | None:
        return "db"

    def get_service(self) -> JsonFileDbAdapter:
        """Returns the singleton instance of the file DB adapter."""
        return self._adapter

    def register(self) -> None:
        """No registration needed as the service is passed via get_service."""
        log.info("JSON DB Addon registered, service is ready.")

    def close(self) -> None:
        """No resources to clean up."""
        log.info("JSON DB Addon closed.")
