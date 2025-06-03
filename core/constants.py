# core/constants.py

from pathlib import Path
from typing import Final

BASE_PATH: str = Path(
    *Path(__file__).resolve().parts[0 : Path(__file__).resolve().parts.index("Qi") + 1]
).as_posix()

CONFIG_FILE: str = Path(Path(BASE_PATH) / "config" / "qi.config.toml").as_posix()

DOTENV_FILE: str = Path(Path(BASE_PATH) / "config" / ".env").as_posix()

HUB_ID: Final[str] = "__hub__"
