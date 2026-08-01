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


def build_button_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_ui")

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_scene(
            message,
            "start",
            "🐉 <b>Врата подземелья открыты.</b>\n\n"
            "Теперь всё приключение управляется кнопками. Выбирай действие в меню внизу — "
            "я стану летописцем, судьёй кубов и голосом мира.",
            MAIN_MENU,
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await send_scene(
            message,
            "start",
            "❓ <b>Как играть</b>\n\n"
            "Нажми «🏕️ Кампания», создай героя и продолжай приключение кнопками меню. "
            "Команды сохранены только как резервный способ управления.",
            MAIN_MENU,
        )

    router.include_router(build_adventure_router(database, store))
    router.include_router(build_combat_router(database, store))
    router.include_router(build_journal_router(database, store))
    return router
