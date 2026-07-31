from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    database_path: Path
    log_level: str = "INFO"

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
        return cls(
            bot_token=token,
            database_path=database_path,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
