"""
Qi addon to provide a JSON file-based database service.
"""

from pathlib import Path

from core.addon.base import AddonRole, QiAddonBase
from core.constants import BASE_PATH
from core.db.file_db import JsonFileDbAdapter
from core.db.manager import qi_db_manager
from core.logger import get_logger

log = get_logger(__name__)


class JsonFileDbAddon(QiAddonBase):
    @property
    def name(self) -> str:
        return "core_json_db"

    @property
    def role(self) -> AddonRole | None:
        return "db"

    def register(self) -> None:
        """
        Initializes the file db adapter and registers it with the db manager.
        """
        log.info("Registering JsonFileDbAdapter as the system's db provider.")

        # Create a data directory in the project root
        data_dir = Path(BASE_PATH) / "data"
        data_dir.mkdir(exist_ok=True)

        adapter = JsonFileDbAdapter(str(data_dir))
        qi_db_manager.set_file_adapter(adapter)

    def close(self) -> None:
        pass
