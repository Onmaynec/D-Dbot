from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.database import Database
from app.gameplay import SHOP_ITEMS, get_shop_item, use_healing_item
from app.generators import generate_character, generate_loot
from app.session import SessionStore
from app.button_ui.common import campaign_context, esc
from app.button_ui.keyboards import (
    BTN_INVENTORY,
    BTN_LOOT,
    BTN_PARTY,
    BTN_SHOP,
    INVENTORY_MENU,
    MAIN_MENU,
    PARTY_MENU,
    inventory_keyboard,
    shop_keyboard,
)
from app.button_ui.media import send_scene

RARITY_ICONS = {"обычная": "⚪", "редкая": "🔵", "эпическая": "🟣", "легендарная": "🟠"}
HEALING_ITEMS = {0: "Зелье лечения", 1: "Большое зелье лечения"}


def build_progression_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_progression")

    async def show_party(message: Message) -> None:
        members = await database.get_party_members(message.chat.id)
        if not members:
            await send_scene(
                message,
                "character",
                "👥 <b>Партия пока пуста.</b>\n\nКаждый игрок может нажать «Вступить в партию» и получить собственного героя.",
                PARTY_MENU,
            )
            return
        lines = []
        for index, member in enumerate(members, start=1):
            character = member["character"]
            lines.append(
                f"{index}. <b>{esc(member['display_name'])}</b> — {esc(character['name'])}\n"
                f"   {esc(character['race'])}, {esc(character['class'])}, уровень {character['level']}"
            )
        await send_scene(
            message,
            "character",
            f"👥 <b>Состав партии: {len(members)}</b>\n\n" + "\n\n".join(lines),
            PARTY_MENU,
        )

    async def show_inventory(message: Message) -> None:
        items = await database.get_inventory(message.chat.id)
        gold = await database.get_gold(message.chat.id)
        if items:
            lines = [
                f"{RARITY_ICONS.get(str(item['rarity']), '⚪')} {esc(item['item_name'])} ×{item['quantity']}"
                for item in items
            ]
            body = "\n".join(lines)
            keyboard = inventory_keyboard(items)
        else:
            body = "Рюкзак пуст. Добывай сокровища или загляни в лавку."
            keyboard = INVENTORY_MENU
        await send_scene(
            message,
            "loot_common",
            f"🎒 <b>Инвентарь партии</b>\n\n💰 Казна: <b>{gold} золотых</b>\n\n{body}",
            keyboard,
        )

    async def show_shop(message: Message) -> None:
        gold = await database.get_gold(message.chat.id)
        lines = [
            f"{index + 1}. <b>{esc(item['name'])}</b> — {item['price']} зм.\n   <i>{esc(item['description'])}</i>"
            for index, item in enumerate(SHOP_ITEMS)
        ]
        await send_scene(
            message,
            "loot_rare",
            f"🏪 <b>Лавка странствующего торговца</b>\n\n💰 В казне: <b>{gold} золотых</b>\n\n"
            + "\n\n".join(lines),
            shop_keyboard(SHOP_ITEMS),
        )

    @router.message(F.text == BTN_PARTY)
    async def party_button(message: Message) -> None:
        await show_party(message)

    @router.callback_query(F.data == "party:show")
    async def party_show(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_party(callback.message)

    @router.callback_query(F.data == "party:join")
    async def party_join(callback: CallbackQuery) -> None:
        current = await database.get_party_member(callback.message.chat.id, callback.from_user.id)
        if current:
            await callback.answer("Ты уже состоишь в этой партии.", show_alert=True)
            await show_party(callback.message)
            return
        character = generate_character()
        await database.upsert_party_member(
            callback.message.chat.id,
            callback.from_user.id,
            callback.from_user.full_name,
            character,
        )
        await store.log(
            callback.message.chat.id,
            "party",
            f"{callback.from_user.full_name} вступает в партию как {character['name']}, {character['class']}",
            payload=character,
        )
        await callback.answer("Герой присоединился к партии!")
        await send_scene(
            callback.message,
            "character",
            f"➕ <b>{esc(callback.from_user.full_name)} вступает в партию!</b>\n\n"
            f"Герой: <b>{esc(character['name'])}</b>\n"
            f"Раса: {esc(character['race'])}\nКласс: {esc(character['class'])}\n"
            f"Уровень: {character['level']} · HP: {character['current_hp']}/{character['max_hp']}",
            PARTY_MENU,
        )

    @router.callback_query(F.data == "party:leave")
    async def party_leave(callback: CallbackQuery) -> None:
        removed = await database.remove_party_member(callback.message.chat.id, callback.from_user.id)
        await callback.answer("Ты покинул партию." if removed else "Тебя нет в составе партии.", show_alert=not removed)
        if removed:
            await store.log(callback.message.chat.id, "party", f"{callback.from_user.full_name} покидает партию")
        await show_party(callback.message)

    @router.message(F.text == BTN_INVENTORY)
    async def inventory_button(message: Message) -> None:
        await show_inventory(message)

    @router.callback_query(F.data == "inventory:show")
    async def inventory_show(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_inventory(callback.message)

    @router.callback_query(F.data.startswith("inventory:use:"))
    async def inventory_use(callback: CallbackQuery) -> None:
        try:
            item_name = HEALING_ITEMS[int(callback.data.rsplit(":", 1)[1])]
        except (KeyError, ValueError):
            await callback.answer("Неизвестный предмет.", show_alert=True)
            return
        character = await database.get_active_character(callback.message.chat.id)
        if not character:
            await callback.answer("Сначала создай основного героя.", show_alert=True)
            return
        if int(character["current_hp"]) >= int(character["max_hp"]):
            await callback.answer("У героя уже полное здоровье.", show_alert=True)
            return
        consumed = await database.consume_inventory_item(callback.message.chat.id, item_name)
        if not consumed:
            await callback.answer("Такого предмета больше нет.", show_alert=True)
            return
        result = use_healing_item(character, item_name)
        await database.update_character(character)
        await store.log(
            callback.message.chat.id,
            "inventory",
            f"Использован предмет {item_name}: восстановлено {result['restored']} HP",
        )
        await callback.answer(f"Восстановлено {result['restored']} HP!")
        await send_scene(
            callback.message,
            "rest",
            f"🧪 <b>{esc(item_name)} использовано</b>\n\n"
            f"{esc(character['name'])} восстанавливает <b>{result['restored']} HP</b>.\n"
            f"Здоровье: {character['current_hp']}/{character['max_hp']}",
            MAIN_MENU,
        )

    @router.message(F.text == BTN_SHOP)
    async def shop_button(message: Message) -> None:
        await show_shop(message)

    @router.callback_query(F.data == "shop:show")
    async def shop_show(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_shop(callback.message)

    @router.callback_query(F.data.startswith("shop:buy:"))
    async def shop_buy(callback: CallbackQuery) -> None:
        try:
            item = get_shop_item(int(callback.data.rsplit(":", 1)[1]))
        except (ValueError, IndexError):
            await callback.answer("Товар исчез с прилавка.", show_alert=True)
            return
        bought, remaining = await database.try_spend_gold(callback.message.chat.id, int(item["price"]))
        if not bought:
            await callback.answer(f"Недостаточно золота. В казне: {remaining}.", show_alert=True)
            return
        await database.add_inventory_item(
            callback.message.chat.id, str(item["name"]), str(item["rarity"]), 1
        )
        await store.log(
            callback.message.chat.id,
            "shop",
            f"Куплен предмет {item['name']} за {item['price']} золотых",
            payload=item,
        )
        await callback.answer("Покупка совершена!")
        await send_scene(
            callback.message,
            "loot_rare",
            f"🛒 <b>Покупка завершена</b>\n\n"
            f"Предмет: {esc(item['name'])}\nЦена: {item['price']} золотых\n"
            f"Осталось в казне: <b>{remaining}</b>",
            shop_keyboard(SHOP_ITEMS),
        )

    @router.message(F.text == BTN_LOOT)
    async def loot_button(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        loot = generate_loot(campaign["name"] if campaign else None)
        await database.add_inventory_item(
            message.chat.id, loot["item"], loot["rarity"], 1
        )
        coin_reward = {"обычная": 5, "редкая": 12, "эпическая": 30, "легендарная": 75}[loot["rarity"]]
        gold = await database.add_gold(message.chat.id, coin_reward)
        icon = RARITY_ICONS[loot["rarity"]]
        scene = "loot_common" if loot["rarity"] == "обычная" else "loot_rare"
        text = (
            f"💎 <b>Добыча добавлена в инвентарь</b>\n\n"
            f"{icon} Редкость: {esc(loot['rarity'])}\nПредмет: <b>{esc(loot['item'])}</b>\n"
            f"Монеты: +{coin_reward} · Казна: {gold} золотых"
        )
        await store.log(
            message.chat.id,
            "loot",
            f"{loot['rarity'].title()} добыча: {loot['item']}; +{coin_reward} золотых",
            payload=loot,
        )
        await send_scene(message, scene, text + suffix, MAIN_MENU)

    return router
