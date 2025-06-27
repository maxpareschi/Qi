"""
Qi addon to provide a mock authentication service for the new core.
"""

from core_new.addon.base import AddonRole, QiAddonBase
from core_new.db.mock_auth import MockAuthAdapter
from core_new.logger import get_logger

log = get_logger("addon.mock_auth")


class NewMockAuthAddon(QiAddonBase):
    """A provider addon that supplies the MockAuthAdapter."""

    def __init__(self):
        self._adapter = MockAuthAdapter()

    @property
    def name(self) -> str:
        return "core_mock_auth"

    @property
    def role(self) -> AddonRole | None:
        return "auth"

    def get_service(self) -> MockAuthAdapter:
        """Returns the singleton instance of the auth adapter."""
        return self._adapter

    def register(self) -> None:
        """No registration needed as the service is passed via get_service."""
        log.info("Mock Auth Addon registered, service is ready.")

    def close(self) -> None:
        """No resources to clean up."""
        log.info("Mock Auth Addon closed.")
