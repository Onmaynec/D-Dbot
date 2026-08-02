from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app import __version__
from app.button_ui import build_button_router
from app.config import Settings
from app.database import Database
from app.handlers import build_router
from app.maintenance import create_database_backup
from app.session import SessionStore

COMMANDS = [
    BotCommand(command="start", description="Открыть игровое меню"),
    BotCommand(command="help", description="Показать правила и кнопки"),
    BotCommand(command="daily", description="Получить ежедневную награду"),
    BotCommand(command="forge", description="Открыть кузницу и разбор предметов"),
    BotCommand(command="tactics", description="Использовать боевые предметы"),
    BotCommand(command="support", description="Вылечить союзника в бою"),
    BotCommand(command="status", description="Проверить версию и состояние данных"),
]


async def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger(__name__)

    database = Database(settings.database_path)
    await database.initialize()
    if settings.backup_on_start:
        try:
            backup_path = await create_database_backup(
                database.path,
                settings.backup_dir,
                settings.backup_keep,
            )
            logger.info("SQLite backup created: %s", backup_path)
        except Exception:
            logger.exception("Unable to create startup SQLite backup")

    store = SessionStore(database)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.include_router(build_button_router(database, store))
    dispatcher.include_router(build_router(database, store))  # резервные slash-команды

    await bot.set_my_commands(COMMANDS)
    logger.info("D&D bot %s is entering the dungeon with button UI", __version__)
    await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
