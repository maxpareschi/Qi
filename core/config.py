# core/config.py

import os
import tomllib
from dataclasses import field  # noqa
from pathlib import Path
from typing import Any, Self, Type

from pydantic import Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
)

from core.constants import BASE_PATH, CONFIG_FILE, DOTENV_FILE


class QiConfigManager(BaseSettings):
    """
    Qi launcher configuration settings.
    """

    # Pydantic configuration settings
    model_config = SettingsConfigDict(
        case_sensitive=False,
        cli_implicit_flags=True,
        cli_kebab_case=True,
        cli_parse_args=True,
        cli_parse_none_str=False,
        env_file=DOTENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        env_prefix="qi_",
        extra="forbid",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Change source priority order (env trumps environment)."""
        toml_data: dict[str, Any] = {}
        if Path(CONFIG_FILE).exists():
            with open(CONFIG_FILE, "rb") as f:
                toml_data = tomllib.load(f).get("qi", {})
        init_settings.init_kwargs = toml_data
        return (dotenv_settings, env_settings, init_settings, file_secret_settings)

    # Core flags
    dev_mode: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    headless: bool = Field(default=False)

    # Network
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)

    # SSL
    ssl_cert_path: str = Field(default="")
    ssl_key_path: str = Field(default="")

    # Base path
    base_path: str = Field(default=BASE_PATH)

    # Addon discovery: always a list of absolute paths
    addon_paths: list[str] | str = Field(default="")

    # Addon dev servers, to be parsed when launching the app in dev mode
    addon_dev_servers: dict[str, dict[str, str]] = Field(default_factory=dict)

    @field_validator("addon_paths", mode="before")
    @classmethod
    def _parse_addon_paths(cls, v: str | list[str]) -> list[str]:
        """
        Parse the addon paths from a string or list of strings and normalize them to absolute paths.
        """
        if isinstance(v, str):
            paths = v.split(os.pathsep)
        elif isinstance(v, list):
            paths = v
        return [Path(p).resolve().as_posix() for p in paths if p]

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, v: str) -> str:
        """
        Normalize the log level to a valid log level.
        """
        return v.upper()

    @field_validator("base_path", mode="before")
    @classmethod
    def _normalize_base_path(cls, v: str) -> str:
        """
        Normalize the base path to an absolute path.
        """
        return Path(v or BASE_PATH).resolve().as_posix()

    @model_validator(mode="after")
    def _dev_mode_setup(self) -> Self:
        """
        If dev mode is enabled, set the log level to DEBUG.
        """
        if self.dev_mode:
            self.log_level = "DEBUG"

        return self


try:
    _config = QiConfigManager()
except SettingsError as e:
    print(e)
    raise SettingsError(
        "Failed to load configuration file. Please check the file is valid and try again."
    )

if _config.dev_mode:
    from pydantic.dataclasses import dataclass as dataclass
else:
    from dataclasses import dataclass as dataclass


qi_config: QiConfigManager = _config
