from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.button_ui.keyboards import COMBAT_MENU
from app.button_ui.media import send_scene
from app.database import Database
from app.session import SessionStore
from app.tactical_items import (
    PHOENIX_FEATHER,
    SHIELD_SCROLL,
    TacticalItemStore,
    combat_effects_text,
    has_living_enemies,
)


def _quantities(items: list[dict]) -> dict[str, int]:
    return {str(item["item_name"]): int(item["quantity"]) for item in items}


def _tactical_keyboard(items: list[dict], state: dict) -> InlineKeyboardMarkup:
    quantities = _quantities(items)
    rows: list[list[InlineKeyboardButton]] = []
    shield_quantity = quantities.get(SHIELD_SCROLL, 0)
    phoenix_quantity = quantities.get(PHOENIX_FEATHER, 0)

    if shield_quantity > 0 and int(state.get("shield_rounds", 0)) <= 0:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🛡️ Активировать свиток ×{shield_quantity}",
                    callback_data="tactics:use:shield",
                )
            ]
        )
    if phoenix_quantity > 0 and not bool(state.get("phoenix_ready", False)):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🔥 Подготовить перо ×{phoenix_quantity}",
                    callback_data="tactics:use:phoenix",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="⚔️ Вернуться к бою", callback_data="combat:status")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_tactical_router(
    database: Database,
    store: SessionStore,
    tactical_store: TacticalItemStore,
) -> Router:
    router = Router(name="button_tactical_items")

    async def show_tactics(message: Message, notice: str = "") -> None:
        state = await store.get_combat(message.chat.id)
        if not state or not has_living_enemies(state):
            await send_scene(
                message,
                "combat",
                "🎒 <b>Боевые предметы доступны только во время активного боя.</b>",
                COMBAT_MENU,
            )
            return

        items = await database.get_inventory(message.chat.id)
        quantities = _quantities(items)
        shield_quantity = quantities.get(SHIELD_SCROLL, 0)
        phoenix_quantity = quantities.get(PHOENIX_FEATHER, 0)
        effects = combat_effects_text(state) or "Активных эффектов пока нет."
        prefix = f"{notice}\n\n" if notice else ""
        await send_scene(
            message,
            "combat",
            prefix
            + "🎒 <b>Тактические предметы</b>\n\n"
            + f"🛡️ Свиток щита: <b>{shield_quantity}</b>\n"
            + f"🔥 Перо феникса: <b>{phoenix_quantity}</b>\n\n"
            + "<b>Активные эффекты</b>\n"
            + effects
            + "\n\nСвиток даёт +2 КД на два хода врагов. "
            + "Перо один раз возвращает героя с половиной максимального HP.",
            _tactical_keyboard(items, state),
        )

    @router.message(Command("tactics"))
    async def tactics_command(message: Message) -> None:
        await show_tactics(message)

    @router.callback_query(F.data == "tactics:show")
    async def tactics_show(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_tactics(callback.message)

    @router.callback_query(F.data.startswith("tactics:use:"))
    async def tactics_use(callback: CallbackQuery) -> None:
        item_code = callback.data.rsplit(":", 1)[1]
        try:
            result = await tactical_store.activate(
                callback.message.chat.id,
                callback.from_user.id,
                item_code,
            )
        except ValueError as error:
            await callback.answer(str(error), show_alert=True)
            return

        if not result.activated or result.state is None:
            await callback.answer(result.reason, show_alert=True)
            await show_tactics(callback.message)
            return

        await store.cache_combat(callback.message.chat.id, result.state)
        await store.log(
            callback.message.chat.id,
            "combat_item",
            f"{callback.from_user.full_name} активирует {result.item_name}",
            payload={"item": result.item_name, "remaining": result.remaining},
        )
        await callback.answer("Предмет активирован!")
        if result.item_name == SHIELD_SCROLL:
            notice = "🛡️ <b>Защитная руна вспыхивает: +2 КД на два хода врагов.</b>"
        else:
            notice = "🔥 <b>Перо феникса готово спасти героя от смертельного удара.</b>"
        await show_tactics(callback.message, notice)

    return router
