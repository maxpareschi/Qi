# core/addon/discovery.py

"""
This module contains functions for discovering and loading addons.
"""

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Type

from core.addon.base import AddonDiscoveryError, AddonLoadError, QiAddonBase
from core.logger import get_logger

log = get_logger(__name__)


def discover_addon_dirs(addon_paths: list[str]) -> dict[str, Path]:
    """
    Scans specified directories for valid addon subdirectories.

    A valid addon directory must contain an `addon.py` file.

    Args:
        addon_paths: A list of paths to directories containing addons.

    Returns:
        A dictionary mapping the addon directory name to its absolute Path.
    """
    discovered = {}
    for path_str in addon_paths:
        path = Path(path_str)
        if not path.is_dir():
            continue
        for child in path.iterdir():
            if child.is_dir() and (child / "addon.py").is_file():
                if child.name in discovered:
                    # For now, the first one discovered wins.
                    log.warning(
                        f"Duplicate addon name '{child.name}' found at "
                        f"'{child.resolve()}'. The existing one at "
                        f"'{discovered[child.name]}' will be used."
                    )
                else:
                    discovered[child.name] = child.resolve()
    return discovered


def load_addon_from_path(addon_name: str, addon_path: Path) -> QiAddonBase:
    """
    Dynamically loads and instantiates an addon from its directory path.

    This function imports the `addon.py` file as a module, finds the first
    class that subclasses `QiAddonBase`, and returns an instance of it.

    Args:
        addon_name: The name of the addon (typically the directory name).
        addon_path: The absolute path to the addon's directory.

    Returns:
        An instantiated addon object.

    Raises:
        AddonLoadError: If the addon cannot be loaded, the class cannot be
                        found, or instantiation fails.
    """
    entry_point = addon_path / "addon.py"
    if not entry_point.is_file():
        raise AddonDiscoveryError(
            f"Addon entry point 'addon.py' not found in {addon_path}"
        )

    # Add the addon's parent directory to sys.path to allow the addon
    # to import its own modules using its package name.
    # e.g., `from my_addon.lib import something`
    parent_dir = str(addon_path.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    module_name = f"{addon_name}.addon"
    try:
        spec = importlib.util.spec_from_file_location(module_name, entry_point)
        if not spec or not spec.loader:
            raise ImportError("Could not create module spec.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as e:
        raise AddonLoadError(f"Failed to import addon '{addon_name}': {e}") from e

    # Find the QiAddonBase subclass in the loaded module
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, QiAddonBase) and obj is not QiAddonBase:
            addon_class: Type[QiAddonBase] = obj
            try:
                instance = addon_class()
                # Basic validation
                if instance.name != addon_name:
                    raise AddonLoadError(
                        f"Addon name mismatch in '{addon_name}': "
                        f"Directory is '{addon_name}', but class `name` is '{instance.name}'."
                    )
                return instance
            except Exception as e:
                raise AddonLoadError(
                    f"Failed to instantiate addon class '{addon_class.__name__}' "
                    f"in '{addon_name}': {e}"
                ) from e

    raise AddonLoadError(
        f"Could not find a QiAddonBase subclass in '{addon_name}/addon.py'."
    )
