# core/constants.py

"""
Constants module.

This module contains a collection of constants that are used throughout the Qi application.
It's also a one to one mapping of env vars available to the application.
"""

from pathlib import Path

QI_BASE_DIR: Path = Path(__file__).resolve().parent.parent
QI_DEV_MODE: bool = False
QI_LOG_LEVEL: str = "INFO"
QI_HEADLESS: bool = False

# DATA
QI_DATA_DIR: Path = QI_BASE_DIR / "data"

# CONFIG
QI_CONFIG_DIR: Path = QI_BASE_DIR / "config"
QI_CONFIG_TOML_FILE: Path = QI_CONFIG_DIR / "qi.config.toml"
QI_CONFIG_ENV_FILE: Path = QI_CONFIG_DIR / "qi.config.env"

# BUS
QI_BUS_REPLY_TIMEOUT: float = 5.0
QI_BUS_MAX_PENDING_REQUESTS_PER_SESSION: int = 100

# SERVER
QI_LOCAL_SERVER_HOST: str = "localhost"
QI_LOCAL_SERVER_PORT: int = 8000
QI_LOCAL_SERVER_SSL_CERT_PATH: str | None = None
QI_LOCAL_SERVER_SSL_KEY_PATH: str | None = None


# BUNDLES
QI_BUNDLES_FILE: Path = QI_CONFIG_DIR / "qi.bundles.toml"
QI_BUNDLES_ACTIVE_BUNDLE: str = "production"
QI_BUNDLES_FALLBACK_ORDER: list[str] = [
    "production",
    "staging",
    "dev",
]

# EXTENSIONS
QI_EXTENSIONS_SEARCH_DIRS: list[Path] = [QI_BASE_DIR / "extensions"]
QI_EXTENSIONS_DEV_SERVERS: dict[str, dict[str, str]] = {}
