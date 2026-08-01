from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.button_ui import build_button_router
from app.config import Settings
from app.database import Database
from app.handlers import build_router
from app.session import SessionStore

COMMANDS = [
    BotCommand(command="start", description="Открыть игровое меню"),
    BotCommand(command="help", description="Показать правила и кнопки"),
]


async def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    database = Database(settings.database_path)
    await database.initialize()
    store = SessionStore(database)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.include_router(build_button_router(database, store))
    dispatcher.include_router(build_router(database, store))  # резервные slash-команды

    await bot.set_my_commands(COMMANDS)
    logging.getLogger(__name__).info("D&D bot is entering the dungeon with button UI")
    await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
