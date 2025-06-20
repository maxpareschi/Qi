# core/constants.py

"""
This module contains the constants for the Qi system.
"""

from pathlib import Path
from typing import Final

# ______________________ BASE ______________________

BASE_PATH: str = Path(
    *Path(__file__).resolve().parts[0 : Path(__file__).resolve().parts.index("Qi") + 1]
).as_posix()

CONFIG_FILE: str = Path(Path(BASE_PATH) / "config" / "qi.config.toml").as_posix()

DOTENV_FILE: str = Path(Path(BASE_PATH) / "config" / ".env").as_posix()


# ______________________ BUNDLES ______________________

BUNDLES_FILE: str = Path(Path(BASE_PATH) / "config" / "bundles.toml").as_posix()

DEFAULT_BUNDLE_NAME: Final[str] = "production"

BUNDLE_FALLBACK_ORDER: list[str] = [DEFAULT_BUNDLE_NAME, "dev"]


# ______________________ HUB ______________________

HUB_ID: Final[str] = "__hub__"
