from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.database import Database
from app.session import SessionStore
from app.button_ui.adventure import build_adventure_router
from app.button_ui.combat import build_combat_router
from app.button_ui.journal import build_journal_router
from app.button_ui.keyboards import MAIN_MENU
from app.button_ui.media import send_scene
from app.button_ui.progression import build_progression_router


def build_button_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_ui")

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_scene(
            message,
            "start",
            "🐉 <b>Врата подземелья открыты.</b>\n\n"
            "Теперь всё приключение управляется кнопками. Собирай партию, покупай снаряжение, "
            "веди инвентарь и сражайся в полноценных раундах с ответными ходами врагов.",
            MAIN_MENU,
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await send_scene(
            message,
            "start",
            "❓ <b>Как играть</b>\n\n"
            "Начни кампанию, создай основного героя, а затем предложи другим игрокам вступить "
            "в партию. Добыча автоматически попадает в общий инвентарь, а золото можно тратить в лавке.",
            MAIN_MENU,
        )

    router.include_router(build_progression_router(database, store))
    router.include_router(build_adventure_router(database, store))
    router.include_router(build_combat_router(database, store))
    router.include_router(build_journal_router(database, store))
    return router
