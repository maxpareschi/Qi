# core/config.py

"""
Config module.

This module provides initial configuration settings for bootstrapping the application.
"""

import os
import sys
from pathlib import Path
from typing import Mapping, Sequence

from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from core.constants import (
    QI_BASE_DIR,
    QI_BUNDLES_ACTIVE_BUNDLE,
    QI_BUNDLES_FALLBACK_ORDER,
    QI_BUNDLES_FILE,
    QI_BUS_MAX_PENDING_REQUESTS_PER_SESSION,
    QI_BUS_REPLY_TIMEOUT,
    QI_CONFIG_DIR,
    QI_CONFIG_ENV_FILE,
    QI_CONFIG_TOML_FILE,
    QI_DATA_DIR,
    QI_DEV_MODE,
    QI_EXTENSIONS_DEV_SERVERS,
    QI_EXTENSIONS_SEARCH_DIRS,
    QI_HEADLESS,
    QI_LOCAL_SERVER_HOST,
    QI_LOCAL_SERVER_PORT,
    QI_LOCAL_SERVER_SSL_CERT_PATH,
    QI_LOCAL_SERVER_SSL_KEY_PATH,
    QI_LOG_LEVEL,
)


def _get_cli_path_value(arg_name: str) -> str | None:
    """
    A safe, naive parser for a specific CLI path-like argument.
    Handles both `--arg /path/to/file` and `--arg=/path/to/file`.
    It does not consume the arguments, allowing Pydantic to parse them later.
    """
    try:
        # Handles `--arg /path/to/file`
        index = sys.argv.index(arg_name)
        if index + 1 < len(sys.argv) and not sys.argv[index + 1].startswith("-"):
            return sys.argv[index + 1]
    except ValueError:
        pass  # Arg not found, proceed to check for other format

    # Handles `--arg=/path/to/file`
    prefix = f"{arg_name}="
    for arg in sys.argv:
        if arg.startswith(prefix):
            return arg.split("=", 1)[1]

    return None


def _get_env_file_path() -> Path:
    """Get the environment file path from cli, environment or default path."""
    cli_path = _get_cli_path_value("--config.env-file")
    if cli_path:
        return Path(cli_path).resolve()
    return Path(os.environ.get("QI_CONFIG_ENV_FILE", QI_CONFIG_ENV_FILE)).resolve()


def _get_toml_file_path() -> Path:
    """Get the TOML file path from cli, environment or default path."""
    cli_path = _get_cli_path_value("--config.toml-file")
    if cli_path:
        return Path(cli_path).resolve()
    return Path(os.environ.get("QI_CONFIG_TOML_FILE", QI_CONFIG_TOML_FILE)).resolve()


def _transfer_config_to_env(
    data: Mapping[str, object],
    *,
    prefix: str = "QI",
    join: str = "_",
    pathsep: str | None = None,
) -> dict[str, str]:
    """
    Recursively flattens *data* into environment variables.

    - Keys become UPPER-CASE and are joined by *join*.
    - Each resulting key is prefixed with *prefix* and that same *join*.
    - All values are turned into str:
        - bool → "1" or "0"
        - list / tuple → path-sep-joined string (default os.pathsep)
        - None → ""
        - everything else → str(value)
    """
    if pathsep is None:
        pathsep = os.pathsep

    env: dict[str, str] = {}

    def walk(node: object, parts: list[str]) -> None:
        if isinstance(node, Mapping):
            for k, v in node.items():
                walk(v, parts + [k])
        else:
            key = f"{prefix}{join}" + join.join(p.upper() for p in parts)
            if isinstance(node, bool):
                value = "1" if node else "0"
            elif isinstance(node, Sequence) and not isinstance(
                node, (str, bytes, bytearray)
            ):
                value = pathsep.join(str(item) for item in node)
            elif node is None:
                value = ""
            else:
                value = str(node)
            env[key] = value

    walk(data, [])
    return env


class QiBaseConfigModel(BaseModel):
    """Paths configuration settings."""

    dir: str | Path = QI_CONFIG_DIR
    toml_file: str | Path = QI_CONFIG_TOML_FILE
    env_file: str | Path = QI_CONFIG_ENV_FILE

    @field_validator("dir", "toml_file", "env_file", mode="before")
    @classmethod
    def _validate_and_resolve_path(cls, v: str | Path) -> Path:
        """Parse the path from a string or path and normalize it to an absolute path."""
        return Path(v).resolve()


class QiDataConfigModel(BaseModel):
    """Data configuration settings."""

    dir: Path = QI_DATA_DIR

    @field_validator("dir", mode="before")
    @classmethod
    def _validate_and_resolve_path(cls, v: str | Path) -> Path:
        """Parse the path from a string or path and normalize it to an absolute path."""
        return Path(v).resolve()


class QiBusConfigModel(BaseModel):
    """Bus configuration settings."""

    reply_timeout: float = QI_BUS_REPLY_TIMEOUT
    max_pending_requests_per_session: int = QI_BUS_MAX_PENDING_REQUESTS_PER_SESSION


class QiLocalServerConfigModel(BaseModel):
    """Local server configuration settings."""

    host: str = QI_LOCAL_SERVER_HOST
    port: int = QI_LOCAL_SERVER_PORT
    ssl_cert_path: str | None = QI_LOCAL_SERVER_SSL_CERT_PATH
    ssl_key_path: str | None = QI_LOCAL_SERVER_SSL_KEY_PATH

    @property
    def use_ssl(self) -> bool:
        """Check if SSL is enabled based on cert and key paths."""
        return bool(self.ssl_cert_path and self.ssl_key_path)


class QiBundlesConfigModel(BaseModel):
    """Bundles configuration settings."""

    file: str | Path = QI_BUNDLES_FILE
    active_bundle: str = QI_BUNDLES_ACTIVE_BUNDLE
    fallback_order: str | list[str] = QI_BUNDLES_FALLBACK_ORDER

    @field_validator("fallback_order", mode="before")
    @classmethod
    def _validate_and_split_string(cls, v: str | list[str]) -> list[str]:
        """Parse the fallback order from a string or list of strings and normalize them to a list of strings."""
        if isinstance(v, str):
            return v.split(os.pathsep)
        return v

    @field_validator("file", mode="before")
    @classmethod
    def _validate_and_resolve_path(cls, v: str | Path) -> Path:
        """Parse the path from a string or path and normalize it to an absolute path."""
        return Path(v).resolve()


class QiExtensionsConfigModel(BaseModel):
    """Extensions configuration settings."""

    search_dirs: list[Path] | str = QI_EXTENSIONS_SEARCH_DIRS
    dev_servers: dict[str, dict[str, str]] = QI_EXTENSIONS_DEV_SERVERS

    @field_validator("search_dirs", mode="before")
    @classmethod
    def _validate_and_resolve_path_list(
        cls, v: str | Path | list[str | Path]
    ) -> list[Path]:
        """
        Parse the addon paths from a string or list of strings/paths and normalize them to absolute paths.
        Filters out empty or whitespace-only path strings before resolving.
        """
        if isinstance(v, str):
            paths_str = v.split(os.pathsep)
        elif isinstance(v, Path):
            paths_str = [v]
        elif isinstance(v, list):
            paths_str = v
        else:
            return []

        resolved_paths = []
        for p_str in paths_str:
            path_str = str(p_str).strip()
            if path_str:
                resolved_paths.append(Path(path_str).resolve())
        return resolved_paths


class QiLaunchConfig(BaseSettings):
    """Qi main launch configuration settings."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        cli_implicit_flags=True,
        cli_kebab_case=True,
        cli_parse_args=True,
        cli_parse_none_str=False,
        env_file=_get_env_file_path(),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        env_nested_delimiter="_",
        env_nested_max_split=1,
        env_prefix="qi_",
        extra="ignore",
        toml_file=_get_toml_file_path(),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Corrected order for: CLI > ENV > DOTENV > TOML > DEFAULTS
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    base_dir: Path = QI_BASE_DIR
    dev_mode: bool = QI_DEV_MODE
    log_level: str = QI_LOG_LEVEL
    headless: bool = QI_HEADLESS
    data: QiDataConfigModel = QiDataConfigModel()
    bus: QiBusConfigModel = QiBusConfigModel()
    local_server: QiLocalServerConfigModel = QiLocalServerConfigModel()
    config: QiBaseConfigModel = QiBaseConfigModel()
    bundles: QiBundlesConfigModel = QiBundlesConfigModel()
    extensions: QiExtensionsConfigModel = QiExtensionsConfigModel()

    @model_validator(mode="after")
    def _validate_and_transfer_to_env(self) -> "QiLaunchConfig":
        """Validate and transfer the model to environment variables."""
        env = _transfer_config_to_env(self.model_dump())
        for k, v in env.items():
            os.environ[k] = v.replace("\\", "/")
        return self
