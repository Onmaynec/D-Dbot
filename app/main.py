from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.config import Settings
from app.database import Database
from app.handlers import build_router
from app.session import SessionStore

COMMANDS = [
    BotCommand(command="campaign", description="Начать новую кампанию"),
    BotCommand(command="character", description="Создать случайного героя"),
    BotCommand(command="quest", description="Получить случайный квест"),
    BotCommand(command="roll", description="Бросить кубик, например /roll d20"),
    BotCommand(command="npc", description="Создать NPC"),
    BotCommand(command="encounter", description="Случайная встреча"),
    BotCommand(command="loot", description="Сгенерировать добычу"),
    BotCommand(command="combat", description="Начать бой"),
    BotCommand(command="attack", description="Атаковать цель"),
    BotCommand(command="spell", description="Сотворить заклинание"),
    BotCommand(command="rest", description="Совершить долгий отдых"),
    BotCommand(command="levelup", description="Повысить уровень"),
    BotCommand(command="journal", description="Показать журнал сессии"),
    BotCommand(command="export", description="Скачать журнал TXT"),
    BotCommand(command="help", description="Показать помощь"),
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

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(database, store))

    await bot.set_my_commands(COMMANDS)
    logging.getLogger(__name__).info("D&D bot is entering the dungeon")
    await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
