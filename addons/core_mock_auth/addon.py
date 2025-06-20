"""
Qi addon to provide a mock authentication service.
"""

from core.addon.base import AddonRole, QiAddonBase
from core.db.manager import qi_db_manager
from core.db.mock_auth import MockAuthAdapter
from core.logger import get_logger

log = get_logger(__name__)


class MockAuthAddon(QiAddonBase):
    @property
    def name(self) -> str:
        return "core_mock_auth"

    @property
    def role(self) -> AddonRole | None:
        return "auth"

    def register(self) -> None:
        """
        Registers the mock auth adapter with the database manager.
        """
        log.info("Registering MockAuthAdapter as the system's auth provider.")
        adapter = MockAuthAdapter()
        qi_db_manager.set_auth_adapter(adapter)

    def close(self) -> None:
        pass
