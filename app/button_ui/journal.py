from __future__ import annotations

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.database import Database
from app.session import SessionStore
from app.button_ui.common import EVENT_ICONS, esc
from app.button_ui.keyboards import BTN_JOURNAL, BTN_MORE, JOURNAL_MENU, MAIN_MENU, MORE_MENU
from app.button_ui.media import journal_thumbnail, send_scene


def build_journal_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_journal")

    async def show_journal(message: Message) -> None:
        entries = await store.get_journal(message.chat.id, limit=8)
        if not entries:
            await send_scene(message, "journal", "📖 Страницы журнала пока пусты.", JOURNAL_MENU)
            return
        lines = []
        for index, entry in enumerate(entries, start=1):
            icon = EVENT_ICONS.get(entry["event_type"], "•")
            lines.append(f"{index}. {icon} {esc(entry['content'])}")
        campaign = await store.get_campaign(message.chat.id)
        title = f"Журнал кампании «{esc(campaign['name'])}»" if campaign else "Журнал текущей сессии"
        await send_scene(message, "journal", f"📖 <b>{title}</b>\n\n" + "\n".join(lines), JOURNAL_MENU)

    async def export_journal(message: Message) -> None:
        entries = await database.get_journal(message.chat.id, limit=10_000)
        campaign = await store.get_campaign(message.chat.id)
        title = campaign["name"] if campaign else "Безымянная сессия"
        lines = [f"ЖУРНАЛ КАМПАНИИ: {title}", "=" * 60, ""]
        for entry in entries:
            date = entry["created_at"].replace("T", " ")
            lines.append(f"[{date}] {entry['event_type'].upper()}: {entry['content']}")
        if not entries:
            lines.append("Журнал пока пуст.")
        document = BufferedInputFile("\n".join(lines).encode("utf-8"), filename="dnd_journal.txt")
        await message.answer_document(
            document=document,
            thumbnail=journal_thumbnail(),
            caption="📜 <b>Летопись кампании сохранена в TXT.</b>",
            reply_markup=MAIN_MENU,
        )

    @router.message(F.text == BTN_JOURNAL)
    async def journal_button(message: Message) -> None:
        await show_journal(message)

    @router.callback_query(F.data == "journal:show")
    async def journal_show(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_journal(callback.message)

    @router.callback_query(F.data == "journal:export")
    async def journal_export(callback: CallbackQuery) -> None:
        await callback.answer("Готовлю летопись…")
        await export_journal(callback.message)

    @router.message(F.text == BTN_MORE)
    async def more_button(message: Message) -> None:
        await send_scene(message, "start", "⚙️ <b>Дополнительные действия</b>", MORE_MENU)

    @router.callback_query(F.data == "menu:help")
    async def menu_help(callback: CallbackQuery) -> None:
        await callback.answer()
        await send_scene(
            callback.message,
            "start",
            "❓ <b>Как играть</b>\n\n"
            "1. Создай мир через «🏕️ Кампания».\n"
            "2. Создай персонажа через «🧙 Герой».\n"
            "3. Получай квесты, встречай NPC и ищи добычу.\n"
            "4. В бою выбирай цель и заклинание кнопками.\n"
            "5. Все события сохраняются в SQLite и доступны в журнале.",
            MAIN_MENU,
        )

    return router
