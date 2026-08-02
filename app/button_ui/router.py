from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app import __version__
from app.button_ui.adventure import build_adventure_router
from app.button_ui.campaign_progress import build_campaign_progress_router
from app.button_ui.combat import build_combat_router
from app.button_ui.daily import build_daily_router
from app.button_ui.dungeon import build_dungeon_router
from app.button_ui.forge import build_forge_router
from app.button_ui.journal import build_journal_router
from app.button_ui.keyboards import MAIN_MENU
from app.button_ui.media import configure_image_mode_resolver, send_scene
from app.button_ui.progression import build_progression_router
from app.button_ui.tactical import build_tactical_router
from app.daily_rewards import DailyRewardStore
from app.database import Database
from app.dungeon_store import DungeonStore
from app.maintenance import check_database, format_bytes
from app.session import SessionStore
from app.tactical_items import TacticalItemStore


def build_button_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_ui")
    dungeon_store = DungeonStore(database.path)
    daily_store = DailyRewardStore(database.path)
    tactical_store = TacticalItemStore(database.path)
    configure_image_mode_resolver(dungeon_store.get_image_mode)

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_scene(
            message,
            "start",
            "🐉 <b>Врата подземелья открыты.</b>\n\n"
            "Теперь доступны партийные боевые раунды, экспедиции по подземельям, боссы, "
            "ежедневные награды, кузница, тактические предметы и настройки изображений. "
            "Всё управление — кнопками и командами.",
            MAIN_MENU,
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await send_scene(
            message,
            "start",
            "❓ <b>Как играть</b>\n\n"
            "Начни кампанию и создай героя. Каждый игрок может вступить в «👥 Партию» и получить "
            "собственного персонажа. В обычном бою каждый живой участник действует один раз за раунд, "
            "после чего начинается общая фаза врагов. "
            "Команда /daily открывает ежедневный сундук партии. "
            "Команда /forge позволяет создавать расходники и разбирать лишнюю добычу в золото. "
            "Во время боя /tactics активирует Свиток щита или Перо феникса. "
            "В «🏰 Подземелье» запускаются постоянные экспедиции с ловушками, добычей и боссами.\n\n"
            "Команда /status показывает версию бота и проверяет целостность SQLite.",
            MAIN_MENU,
        )

    @router.message(Command("status"))
    async def status_handler(message: Message) -> None:
        health = await check_database(database.path)
        icon = "✅" if health.ok else "⚠️"
        await message.answer(
            f"🩺 <b>D&D Telegram Master v{__version__}</b>\n\n"
            f"{icon} SQLite: {health.message}\n"
            f"💾 Размер данных: {format_bytes(health.size_bytes)}\n"
            "🛡️ Резервная копия создаётся при каждом запуске бота."
        )

    router.include_router(build_dungeon_router(database, store, dungeon_store))
    router.include_router(build_daily_router(store, daily_store))
    router.include_router(build_forge_router(database, store))
    router.include_router(build_tactical_router(database, store, tactical_store))
    router.include_router(build_progression_router(database, store))
    # Этот роутер стоит перед старым приключенческим модулем и заменяет прежнюю
    # одноразовую генерацию квестов полноценной системой активных контрактов.
    router.include_router(build_campaign_progress_router(database, store))
    router.include_router(build_adventure_router(database, store))
    router.include_router(build_combat_router(database, store))
    router.include_router(build_journal_router(database, store))
    return router
