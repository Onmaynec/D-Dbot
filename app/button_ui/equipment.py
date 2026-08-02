from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.button_ui.common import divider, esc, rarity_icon
from app.button_ui.keyboards import BTN_EQUIPMENT
from app.button_ui.media import send_scene
from app.equipment import (
    EQUIPMENT,
    EQUIPMENT_BY_CODE,
    SLOT_NAMES,
    EquipmentItem,
    EquipmentStore,
)


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗡️ Оружие", callback_data="eq:shop:weapon"),
                InlineKeyboardButton(text="🛡️ Броня", callback_data="eq:shop:armor"),
            ],
            [
                InlineKeyboardButton(text="💍 Талисманы", callback_data="eq:shop:trinket"),
                InlineKeyboardButton(text="🎒 Мои вещи", callback_data="eq:owned"),
            ],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="eq:show")],
        ]
    )


def _shop_keyboard(slot: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"Купить · {item.name} · {item.price} зм.",
                callback_data=f"eq:buy:{item.code}",
            )
        ]
        for item in EQUIPMENT
        if item.slot == slot
    ]
    rows.append([InlineKeyboardButton(text="↩️ К экипировке", callback_data="eq:show")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _owned_keyboard(owned: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in owned:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Надеть · {item['name']} ×{item['quantity']}",
                    callback_data=f"eq:equip:{item['code']}",
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(text="Снять оружие", callback_data="eq:unequip:weapon"),
                InlineKeyboardButton(text="Снять броню", callback_data="eq:unequip:armor"),
            ],
            [InlineKeyboardButton(text="Снять талисман", callback_data="eq:unequip:trinket")],
            [InlineKeyboardButton(text="↩️ К экипировке", callback_data="eq:show")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _item_stats(item: EquipmentItem) -> str:
    parts: list[str] = []
    if item.damage_bonus:
        parts.append(f"физ. урон +{item.damage_bonus}")
    if item.spell_damage_bonus:
        parts.append(f"маг. урон +{item.spell_damage_bonus}")
    if item.armor_bonus:
        parts.append(f"КД +{item.armor_bonus}")
    if item.guard_bonus:
        parts.append(f"защита +{item.guard_bonus}")
    return " · ".join(parts) or "без боевых бонусов"


def build_equipment_router(store: EquipmentStore) -> Router:
    router = Router(name="button_equipment_v5")

    async def show_overview(message: Message, user_id: int) -> None:
        snapshot = await store.snapshot(message.chat.id, user_id)
        character = snapshot["character"]
        if character is None:
            text = (
                "🧰 <b>Снаряжение героя</b>\n\n"
                "Сначала создай героя и вступи в «👥 Партию». После этого оружие, броня "
                "и талисманы будут закрепляться за твоим персонажем."
            )
        else:
            equipped = snapshot["equipped"]
            bonuses = snapshot["bonuses"]
            lines = [
                f"🧙 Герой: <b>{esc(character['name'])}</b>",
                f"💰 Общая казна: <b>{snapshot['balance']} золота</b>",
                divider(),
                "<b>Надето</b>",
            ]
            for slot in ("weapon", "armor", "trinket"):
                lines.append(
                    f"• {SLOT_NAMES[slot]}: <b>{esc(equipped.get(slot, 'пусто'))}</b>"
                )
            lines.extend(
                [
                    "",
                    "<b>Итоговые бонусы</b>",
                    f"⚔️ Физический урон: <b>+{bonuses['damage']}</b>",
                    f"🔮 Урон магии: <b>+{bonuses['spell_damage']}</b>",
                    f"🛡️ Класс доспеха: <b>+{bonuses['armor']}</b>",
                    f"🧱 Защитная стойка: <b>+{bonuses['guard']}</b>",
                    "",
                    "<i>Менять экипировку во время боя нельзя.</i>",
                ]
            )
            text = "\n".join(lines)
        await send_scene(message, "equipment", text, _main_keyboard())

    async def show_shop(message: Message, slot: str) -> None:
        title = SLOT_NAMES.get(slot, "Снаряжение")
        items = [item for item in EQUIPMENT if item.slot == slot]
        lines = [f"🛒 <b>Лавка: {title}</b>", ""]
        for item in items:
            lines.extend(
                [
                    f"{rarity_icon(item.rarity)} <b>{esc(item.name)}</b> · {item.price} зм.",
                    f"{_item_stats(item)}",
                    f"<i>{esc(item.description)}</i>",
                    "",
                ]
            )
        await send_scene(message, "equipment", "\n".join(lines).rstrip(), _shop_keyboard(slot))

    async def show_owned(message: Message, user_id: int) -> None:
        snapshot = await store.snapshot(message.chat.id, user_id)
        owned = snapshot["owned"]
        if not owned:
            text = (
                "🎒 <b>Личное снаряжение пусто</b>\n\n"
                "Купи оружие, броню или талисман. Расходники по-прежнему хранятся "
                "в общем инвентаре партии."
            )
        else:
            lines = ["🎒 <b>Снаряжение героя</b>", ""]
            for item in owned:
                lines.append(
                    f"{rarity_icon(item['rarity'])} <b>{esc(item['name'])}</b> ×{item['quantity']}\n"
                    f"{esc(_item_stats(EQUIPMENT_BY_CODE[item['code']]))}"
                )
            text = "\n\n".join(lines)
        await send_scene(message, "equipment", text, _owned_keyboard(owned))

    @router.message(Command("equipment"))
    @router.message(F.text == BTN_EQUIPMENT)
    async def equipment_entry(message: Message) -> None:
        if message.from_user is None:
            return
        await show_overview(message, message.from_user.id)

    @router.callback_query(F.data == "eq:show")
    async def equipment_show(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_overview(callback.message, callback.from_user.id)

    @router.callback_query(F.data.startswith("eq:shop:"))
    async def equipment_shop(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_shop(callback.message, callback.data.rsplit(":", 1)[1])

    @router.callback_query(F.data == "eq:owned")
    async def equipment_owned(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_owned(callback.message, callback.from_user.id)

    @router.callback_query(F.data.startswith("eq:buy:"))
    async def equipment_buy(callback: CallbackQuery) -> None:
        code = callback.data.rsplit(":", 1)[1]
        result = await store.buy(callback.message.chat.id, callback.from_user.id, code)
        await callback.answer(result.reason, show_alert=not result.ok)
        if result.ok and result.item:
            await send_scene(
                callback.message,
                "loot_rare",
                f"✅ <b>Покупка завершена</b>\n\n"
                f"Получено: {rarity_icon(result.item.rarity)} <b>{esc(result.item.name)}</b>\n"
                f"Эффект: {esc(_item_stats(result.item))}\n"
                f"Осталось в казне: <b>{result.balance} золота</b>\n\n"
                "Открой «Мои вещи» и надень предмет.",
                _main_keyboard(),
            )

    @router.callback_query(F.data.startswith("eq:equip:"))
    async def equipment_equip(callback: CallbackQuery) -> None:
        code = callback.data.rsplit(":", 1)[1]
        result = await store.equip(callback.message.chat.id, callback.from_user.id, code)
        await callback.answer(result.reason, show_alert=not result.ok)
        await show_overview(callback.message, callback.from_user.id)

    @router.callback_query(F.data.startswith("eq:unequip:"))
    async def equipment_unequip(callback: CallbackQuery) -> None:
        slot = callback.data.rsplit(":", 1)[1]
        result = await store.unequip(callback.message.chat.id, callback.from_user.id, slot)
        await callback.answer(result.reason, show_alert=not result.ok)
        await show_overview(callback.message, callback.from_user.id)

    return router
