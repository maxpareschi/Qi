# core/config.py

import os
import tomllib
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_PATH = Path(
    *Path(__file__).resolve().parts[0 : Path(__file__).resolve().parts.index("Qi") + 1]
)
CONFIG_FILE = BASE_PATH / "config" / "qi.config.toml"
ENV_FILE = BASE_PATH / "config" / ".env"


def load_toml_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        data = tomllib.load(f)
    return data.get("qi", {})


class QiSettings(BaseSettings):
    def __init__(self, *args, **kwargs):
        self.cleanup_env()
        super().__init__(*args, **kwargs)

    # Pydantic configuration settings
    model_config = SettingsConfigDict(
        env_file=ENV_FILE.as_posix(),
        env_file_encoding="utf-8",
        env_prefix="qi_",
        case_sensitive=False,
        extra="forbid",
    )

    # Core flags
    dev_mode: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Network
    local_server: str = Field(default="127.0.0.1")
    local_port: int = Field(default=8000)

    # SSL
    ssl_cert_path: str = Field(default="")
    ssl_key_path: str = Field(default="")

    # Addon discovery: always a list of absolute paths
    addon_paths: list[str] | str = Field(default_factory=list)

    @field_validator("addon_paths", mode="before")
    @classmethod
    def _parse_addon_paths(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            paths = v.split(os.pathsep)
        elif isinstance(v, list):
            paths = v
        else:
            return []
        return [Path(p).resolve().as_posix() for p in paths if p]

    def cleanup_env(self) -> None:
        for field in self.model_json_schema()["properties"].keys():
            os.environ.pop(f"QI_{field.upper()}", None)


_config = QiSettings(**{**load_toml_config(CONFIG_FILE), **QiSettings().model_dump()})

if _config.dev_mode:
    _config.log_level = "DEBUG"

config: QiSettings = _config


# Monkey-patch @dataclass for dev mode
if config.dev_mode:
    import dataclasses

    from pydantic.dataclasses import dataclass as pydantic_dataclass

    dataclasses.dataclass = pydantic_dataclass
