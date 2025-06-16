class AddonManagerError(Exception):
    """Base exception for the Addon Manager."""

    pass


class AddonDiscoveryError(AddonManagerError):
    """Raised when an addon cannot be discovered from its path."""

    pass


class AddonLoadError(AddonManagerError):
    """Raised when an addon module fails to load or instantiate."""

    pass


class MissingProviderError(AddonManagerError):
    """Raised when a required provider addon (e.g., 'auth' or 'db') is not found."""

    def __init__(self, role: str):
        self.role = role
        super().__init__(f"Mandatory provider addon with role '{role}' not found.")


class DuplicateRoleError(AddonManagerError):
    """Raised when multiple addons are found for a unique role."""

    def __init__(self, role: str, addons: list[str]):
        self.role = role
        self.addons = addons
        super().__init__(
            f"Found multiple addons for unique role '{role}': {', '.join(addons)}"
        )
