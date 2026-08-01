from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.database import Database
from app.dungeon_store import DungeonStore
from app.session import SessionStore
from app.button_ui.adventure import build_adventure_router
from app.button_ui.campaign_progress import build_campaign_progress_router
from app.button_ui.combat import build_combat_router
from app.button_ui.dungeon import build_dungeon_router
from app.button_ui.journal import build_journal_router
from app.button_ui.keyboards import MAIN_MENU
from app.button_ui.media import configure_image_mode_resolver, send_scene
from app.button_ui.progression import build_progression_router


def build_button_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_ui")
    dungeon_store = DungeonStore(database.path)
    configure_image_mode_resolver(dungeon_store.get_image_mode)

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_scene(
            message,
            "start",
            "🐉 <b>Врата подземелья открыты.</b>\n\n"
            "Теперь доступны полноценные экспедиции по подземельям, комнаты с ловушками и сокровищами, "
            "битвы с боссами и настройки качества изображений. Всё управление — кнопками.",
            MAIN_MENU,
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await send_scene(
            message,
            "start",
            "❓ <b>Как играть</b>\n\n"
            "Начни кампанию и создай героя. В разделе «🏰 Подземелье» запускаются постоянные экспедиции: "
            "исследуй комнаты, сохраняй добычу, отступай или сражайся с финальным боссом. "
            "В «🎛️ Настройки» можно выбрать сложность и режим изображений без сжатия.",
            MAIN_MENU,
        )

    router.include_router(build_dungeon_router(database, store, dungeon_store))
    router.include_router(build_progression_router(database, store))
    # Этот роутер стоит перед старым приключенческим модулем и заменяет прежнюю
    # одноразовую генерацию квестов полноценной системой активных контрактов.
    router.include_router(build_campaign_progress_router(database, store))
    router.include_router(build_adventure_router(database, store))
    router.include_router(build_combat_router(database, store))
    router.include_router(build_journal_router(database, store))
    return router
