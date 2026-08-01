from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} должен быть true/false, 1/0, yes/no или on/off")


def _env_positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} должен быть целым числом") from error
    if value < 1:
        raise RuntimeError(f"{name} должен быть не меньше 1")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    database_path: Path
    log_level: str = "INFO"
    backup_dir: Path = Path("data/backups")
    backup_keep: int = 7
    backup_on_start: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "BOT_TOKEN не задан. Скопируйте .env.example в .env и добавьте токен BotFather."
            )

        database_path = Path(os.getenv("DATABASE_PATH", "data/dnd_bot.sqlite3"))
        database_path.parent.mkdir(parents=True, exist_ok=True)
        backup_on_start = _env_bool("BACKUP_ON_START", True)
        backup_dir = Path(os.getenv("BACKUP_DIR", "data/backups"))
        if backup_on_start:
            backup_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            bot_token=token,
            database_path=database_path,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            backup_dir=backup_dir,
            backup_keep=_env_positive_int("BACKUP_KEEP", 7),
            backup_on_start=backup_on_start,
        )
