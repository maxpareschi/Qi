# core/config.py

"""
This module contains the configuration for the Qi system.
"""

import os
import tomllib
from pathlib import Path
from typing import Any, Final, Self, Type

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
)

from core.constants import (
    BASE_PATH,
    BUNDLE_FALLBACK_ORDER,
    BUNDLES_FILE,
    CONFIG_FILE,
    DEFAULT_BUNDLE_NAME,
    DOTENV_FILE,
)


class QiLaunchConfig(BaseSettings):
    """
    Qi launcher configuration settings.
    """

    # Pydantic configuration settings
    model_config = SettingsConfigDict(
        case_sensitive=False,
        cli_implicit_flags=True,
        cli_kebab_case=True,
        cli_parse_args=False,
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
        toml_data: dict[str, Any] = {}
        config_path = Path(CONFIG_FILE)
        if config_path.exists():
            try:
                with open(config_path, "rb") as f:
                    toml_data = tomllib.load(f).get("qi", {})
            except tomllib.TOMLDecodeError as e:
                raise SettingsError(f"Error parsing TOML file: {e}")
            except OSError as e:
                # Using print because logger is not available here to avoid circular import.
                print(
                    f"WARNING: Could not read config file at '{config_path}': {e}. Proceeding with defaults."
                )

        # Values from TOML file should override constructor arguments.
        # We start with constructor args and then update with TOML data.
        merged_init_data = init_settings.init_kwargs.copy()
        merged_init_data.update(toml_data)
        init_settings.init_kwargs = merged_init_data

        return (
            env_settings,  # Highest priority: environment variables
            dotenv_settings,  # Next: .env file
            init_settings,  # Then: constructor args > TOML file
            file_secret_settings,  # Then: secrets
        )

    # Core flags
    dev_mode: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    headless: bool = Field(default=False)

    # Network
    host: str = Field(default="localhost")
    port: int = Field(default=8000)

    # SSL
    ssl_cert_path: str = Field(default="")
    ssl_key_path: str = Field(default="")

    # Base path
    base_path: str = Field(default=BASE_PATH)

    # Path to the bundles configuration file
    bundles_file: str = Field(default=BUNDLES_FILE)

    # Default bundle settings
    default_bundle_name: str = Field(default=DEFAULT_BUNDLE_NAME)
    bundle_fallback_order: list[str] = Field(
        default_factory=lambda: BUNDLE_FALLBACK_ORDER
    )

    # Addon discovery: always a list of absolute paths
    addon_paths: list[str] | str = Field(
        default_factory=lambda: [os.path.join(BASE_PATH, "addons")]
    )

    # Addon dev servers, to be parsed when launching the app in dev mode
    addon_dev_servers: dict[str, dict[str, str]] = Field(default_factory=dict)

    # Reply timeout
    reply_timeout: float = Field(default=5.0)

    # Pending requests per session
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

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, v: str) -> str:
        """
        Normalize the log level to a valid log level.
        """
        return v.upper()

    @field_validator("base_path", "bundles_file", mode="before")
    @classmethod
    def _normalize_path(cls, v: str, info: "ValidationInfo") -> str:
        """
        Normalize a path to an absolute path.
        If the path doesn't exist, it uses the absolute path without resolving symlinks.
        Relative paths are resolved from the project's BASE_PATH.
        """
        if not v:
            default_map = {"base_path": BASE_PATH, "bundles_file": BUNDLES_FILE}
            v = default_map.get(info.field_name, "")

        path_obj = Path(v)

        # If the path is not absolute, make it relative to the project root
        if not path_obj.is_absolute():
            path_obj = Path(BASE_PATH) / path_obj

        try:
            # First, attempt to get a fully resolved, existing path
            return path_obj.resolve(strict=True).as_posix()
        except (FileNotFoundError, RuntimeError):
            # If resolve fails, fall back to the absolute path without checking existence
            return path_obj.absolute().as_posix()

    @model_validator(mode="after")
    def _dev_mode_setup(self) -> Self:
        """
        If dev mode is enabled, set the log level to DEBUG.
        """
        if self.dev_mode:
            self.log_level = "DEBUG"

        return self


try:
    qi_launch_config: Final[QiLaunchConfig] = QiLaunchConfig()

except SettingsError as e:
    raise SettingsError(
        f"Failed to load configuration file. Please check the file is valid and try again. {e}"
    )
