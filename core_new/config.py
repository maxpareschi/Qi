"""
Configuration for Qi.

This module provides configuration settings for the Qi application.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base paths
BASE_PATH = Path(__file__).resolve().parent.parent
CONFIG_FILE = os.path.join(BASE_PATH, "config", "qi.config.toml")
DOTENV_FILE = os.path.join(BASE_PATH, "config", ".env")
BUNDLES_FILE = os.path.join(BASE_PATH, "config", "bundles.toml")
DATA_DIR = os.path.join(BASE_PATH, "data")

# Default values
DEFAULT_BUNDLE_NAME = "production"
BUNDLE_FALLBACK_ORDER = [DEFAULT_BUNDLE_NAME, "dev"]


class ServerConfig(BaseModel):
    """Server configuration settings."""

    host: str = "localhost"
    port: int = 8000
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None

    @property
    def use_ssl(self) -> bool:
        """Check if SSL is enabled based on cert and key paths."""
        return bool(self.ssl_cert_path and self.ssl_key_path)


class AppConfig(BaseSettings):
    """
    Application configuration settings.

    This class loads settings from environment variables, .env file, and config file.
    """

    # Pydantic configuration
    model_config = SettingsConfigDict(
        env_file=DOTENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="qi_",
        extra="ignore",
    )

    # Core settings
    dev_mode: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    headless: bool = Field(default=False)

    # Server settings
    server_host: str = Field(default="localhost")
    server_port: int = Field(default=8000)
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None

    # Paths
    base_path: str = Field(default=str(BASE_PATH))
    config_file: str = Field(default=CONFIG_FILE)
    bundles_file: str = Field(default=BUNDLES_FILE)
    data_dir: str = Field(default=DATA_DIR)

    # Bundle settings
    default_bundle_name: str = Field(default=DEFAULT_BUNDLE_NAME)
    bundle_fallback_order: List[str] = Field(
        default_factory=lambda: BUNDLE_FALLBACK_ORDER
    )

    # Addon settings
    addon_paths: List[str] = Field(
        default_factory=lambda: [os.path.join(BASE_PATH, "addons")]
    )
    addon_dev_servers: Dict[str, Dict[str, str]] = Field(default_factory=dict)

    # Messaging settings
    reply_timeout: float = Field(default=5.0)
    max_pending_requests_per_session: int = Field(default=100)

    @field_validator("addon_paths", mode="before")
    @classmethod
    def _parse_addon_paths(cls, v: str | list[str]) -> list[str]:
        """
        Parse the addon paths from a string or list of strings and normalize them to absolute paths.
        Filters out empty or whitespace-only path strings before resolving.
        """
        if isinstance(v, str):
            paths_str = v.split(os.pathsep)
        elif isinstance(v, list):
            paths_str = v
        else:  # Should not happen with type hints, but good for robustness
            return []

        resolved_paths = []
        for p_str in paths_str:
            if (
                p_str and p_str.strip()
            ):  # Check if string is not empty and not just whitespace
                resolved_paths.append(Path(p_str.strip()).resolve().as_posix())
        return resolved_paths

    def __init__(self, **kwargs):
        """
        Initialize the configuration.

        This method loads settings from the config file and merges them with
        the provided kwargs and environment variables.
        """
        # Load settings from config file if it exists
        config_data = {}
        config_path = kwargs.get("config_file", CONFIG_FILE)

        try:
            if os.path.exists(config_path):
                with open(config_path, "rb") as f:
                    config_data = tomllib.load(f)
        except Exception as e:
            print(f"Error loading config file: {e}")

        # Merge config file settings with kwargs
        merged_kwargs = {**config_data.get("qi", {}), **kwargs}

        # Initialize with merged settings
        super().__init__(**merged_kwargs)

        # Update log level based on dev_mode
        if self.dev_mode and self.log_level == "INFO":
            self.log_level = "DEBUG"

    @property
    def server(self) -> ServerConfig:
        """
        Get the server configuration.

        Returns:
            A ServerConfig object with the server settings.
        """
        return ServerConfig(
            host=self.server_host,
            port=self.server_port,
            ssl_cert_path=self.ssl_cert_path,
            ssl_key_path=self.ssl_key_path,
        )


# Create a singleton instance
app_config = AppConfig()
