from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.button_ui.common import esc
from app.button_ui.media import send_scene
from app.database import Database
from app.forge import ForgeSnapshot, ForgeStore, item_code, salvage_value
from app.session import SessionStore

RARITY_ICONS = {
    "обычная": "⚪",
    "редкая": "🔵",
    "эпическая": "🟣",
    "легендарная": "🟠",
}


def _forge_keyboard(snapshot: ForgeSnapshot) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for status in snapshot.recipes:
        icon = "✅" if status.available else "🔒"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} Создать: {status.recipe.name}",
                    callback_data=f"forge:craft:{status.recipe.code}",
                )
            ]
        )

    for item in snapshot.inventory[:10]:
        name = str(item["item_name"])
        rarity = str(item["rarity"])
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🔥 Разобрать: {name} (+{salvage_value(rarity)} зм.)",
                    callback_data=f"forge:salvage:{item_code(name)}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🔄 Обновить кузницу", callback_data="forge:show")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _forge_text(snapshot: ForgeSnapshot) -> str:
    lines = [
        "⚒️ <b>Кузница Чёрного Молота</b>",
        "",
        f"💰 Казна партии: <b>{snapshot.gold_balance} золотых</b>",
        "",
        "<b>Рецепты</b>",
    ]
    for status in snapshot.recipes:
        recipe = status.recipe
        ingredients = ", ".join(f"{esc(name)} ×{quantity}" for name, quantity in recipe.ingredients.items())
        state = "готово" if status.available else "не хватает ресурсов"
        lines.extend(
            [
                f"• <b>{esc(recipe.name)}</b> — {recipe.gold_cost} зм.",
                f"  {ingredients}",
                f"  <i>{esc(recipe.description)} · {state}</i>",
            ]
        )

    lines.extend(["", "<b>Разбор предметов</b>"])
    if snapshot.inventory:
        for item in snapshot.inventory[:10]:
            rarity = str(item["rarity"])
            icon = RARITY_ICONS.get(rarity, "⚪")
            lines.append(
                f"{icon} {esc(item['item_name'])} ×{item['quantity']} "
                f"→ {salvage_value(rarity)} зм. за единицу"
            )
        if len(snapshot.inventory) > 10:
            lines.append(f"<i>Показаны первые 10 из {len(snapshot.inventory)} предметов.</i>")
    else:
        lines.append("Инвентарь пуст — разбирать пока нечего.")
    return "\n".join(lines)


def build_forge_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_forge")
    forge = ForgeStore(database.path)

    async def show_forge(message: Message) -> None:
        snapshot = await forge.snapshot(message.chat.id)
        await send_scene(message, "loot_rare", _forge_text(snapshot), _forge_keyboard(snapshot))

    @router.message(Command("forge"))
    async def forge_command(message: Message) -> None:
        await show_forge(message)

    @router.callback_query(F.data == "forge:show")
    async def forge_show(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_forge(callback.message)

    @router.callback_query(F.data.startswith("forge:craft:"))
    async def forge_craft(callback: CallbackQuery) -> None:
        recipe_code = callback.data.rsplit(":", 1)[1]
        try:
            result = await forge.craft(callback.message.chat.id, callback.from_user.id, recipe_code)
        except ValueError:
            await callback.answer("Рецепт больше недоступен.", show_alert=True)
            return

        if not result.crafted:
            missing = ", ".join(f"{name} ×{quantity}" for name, quantity in result.missing.items())
            reason = f"Не хватает: {missing}." if missing else "Недостаточно золота."
            await callback.answer(reason, show_alert=True)
            return

        await store.log(
            callback.message.chat.id,
            "forge",
            f"Создан предмет {result.recipe.name} за {result.recipe.gold_cost} золотых",
            payload={
                "recipe": result.recipe.code,
                "ingredients": result.recipe.ingredients,
                "gold_cost": result.recipe.gold_cost,
            },
        )
        await callback.answer("Предмет создан!")
        await callback.message.answer(
            f"⚒️ <b>Ковка завершена</b>\n\n"
            f"Создано: <b>{esc(result.recipe.name)}</b>\n"
            f"Осталось в казне: <b>{result.gold_balance}</b>"
        )
        await show_forge(callback.message)

    @router.callback_query(F.data.startswith("forge:salvage:"))
    async def forge_salvage(callback: CallbackQuery) -> None:
        code = callback.data.rsplit(":", 1)[1]
        result = await forge.salvage(callback.message.chat.id, callback.from_user.id, code)
        if not result.salvaged:
            await callback.answer("Предмет уже исчез или список устарел.", show_alert=True)
            return

        await store.log(
            callback.message.chat.id,
            "forge",
            f"Разобран предмет {result.item_name}; получено {result.gold_received} золотых",
            payload={
                "item": result.item_name,
                "rarity": result.rarity,
                "gold_received": result.gold_received,
            },
        )
        await callback.answer(f"+{result.gold_received} золотых")
        await callback.message.answer(
            f"🔥 <b>Предмет разобран</b>\n\n"
            f"{esc(result.item_name)} превращён в <b>{result.gold_received} золотых</b>.\n"
            f"Казна партии: <b>{result.gold_balance}</b>"
        )
        await show_forge(callback.message)

    return router
