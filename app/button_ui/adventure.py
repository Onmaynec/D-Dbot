from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.database import Database
from app.dice import parse_and_roll
from app.generators import (
    generate_campaign,
    generate_character,
    generate_encounter,
    generate_loot,
    generate_npc,
    generate_quest,
)
from app.session import SessionStore
from app.button_ui.common import campaign_context, character_text, clean_html, esc, signed
from app.button_ui.keyboards import (
    BTN_CAMPAIGN,
    BTN_CANCEL,
    BTN_CHARACTER,
    BTN_DICE,
    BTN_ENCOUNTER,
    BTN_LOOT,
    BTN_NPC,
    BTN_QUEST,
    CAMPAIGN_MENU,
    CANCEL_MENU,
    CHARACTER_MENU,
    DICE_MENU,
    MAIN_MENU,
)
from app.button_ui.media import send_scene


class CampaignInput(StatesGroup):
    name = State()


def build_adventure_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_adventure")

    async def show_campaign(message: Message) -> None:
        campaign = await store.get_campaign(message.chat.id)
        if not campaign:
            await send_scene(
                message,
                "campaign",
                "🏕️ <b>Кампания ещё не начата.</b>\n\nНажми кнопку ниже, чтобы дать имя новой легенде.",
                CAMPAIGN_MENU,
            )
            return
        factions = "\n".join(f"• {esc(name)}" for name in campaign["factions"])
        await send_scene(
            message,
            "campaign",
            f"🏕️ <b>{esc(campaign['name'])}</b>\n\nМир: {esc(campaign['world_name'])}\n"
            f"Жанр: {esc(campaign['world_type'])}\n\n<b>Фракции:</b>\n{factions}",
            CAMPAIGN_MENU,
        )

    async def create_campaign(message: Message, title: str) -> None:
        campaign = generate_campaign(title)
        await store.set_campaign(message.chat.id, campaign)
        factions = "\n".join(f"• {esc(name)}" for name in campaign["factions"])
        text = (
            f"🌍 <b>Начинается кампания «{esc(campaign['name'])}»</b>\n\n"
            f"Мир: <b>{esc(campaign['world_name'])}</b>\nЖанр: {esc(campaign['world_type'])}\n\n"
            f"<b>Три силы уже делят судьбу мира:</b>\n{factions}\n\n"
            "Где-то вдали гремит первый гром. История ждёт своих героев."
        )
        await store.log(message.chat.id, "campaign", clean_html(text), payload=campaign)
        await send_scene(message, "campaign", text, MAIN_MENU)

    async def show_character(message: Message) -> None:
        character = await database.get_active_character(message.chat.id)
        if not character:
            await send_scene(
                message,
                "character",
                "🧙 <b>У тебя ещё нет героя.</b>\n\nСоздай персонажа одной кнопкой.",
                CHARACTER_MENU,
            )
            return
        _, suffix = await campaign_context(store, message.chat.id)
        await send_scene(message, "character", character_text(character) + suffix, CHARACTER_MENU)

    async def create_character(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        character = generate_character()
        character["id"] = await database.add_character(
            message.chat.id,
            campaign["name"] if campaign else None,
            character,
        )
        await store.log(
            message.chat.id,
            "character",
            f"Создан персонаж: {character['name']}, {character['race']} {character['class']}",
            payload=character,
        )
        await send_scene(message, "character", character_text(character) + suffix, CHARACTER_MENU)

    async def roll_dice(message: Message, notation: str) -> None:
        try:
            result = parse_and_roll(notation)
        except ValueError as error:
            await send_scene(message, "attack", f"⚠️ {esc(error)}", DICE_MENU)
            return
        rolls = ", ".join(map(str, result.rolls))
        modifier = f" {signed(result.modifier)}" if result.modifier else ""
        _, suffix = await campaign_context(store, message.chat.id)
        await store.log(
            message.chat.id,
            "roll",
            f"{result.notation}: {result.total} ({rolls})",
            payload={"notation": result.notation, "rolls": list(result.rolls), "modifier": result.modifier, "total": result.total},
        )
        await send_scene(
            message,
            "attack",
            f"🎲 <b>Кости ударяются о стол…</b>\n\n<code>{esc(result.notation)}</code>: "
            f"[{rolls}]{modifier} = <b>{result.total}</b>{suffix}",
            DICE_MENU,
        )

    @router.message(F.text == BTN_CAMPAIGN)
    async def campaign_button(message: Message) -> None:
        await show_campaign(message)

    @router.callback_query(F.data == "campaign:new")
    async def new_campaign(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        await state.set_state(CampaignInput.name)
        await send_scene(callback.message, "campaign", "✍️ <b>Напиши название новой кампании.</b>", CANCEL_MENU)

    @router.callback_query(F.data == "campaign:show")
    async def current_campaign(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_campaign(callback.message)

    @router.message(CampaignInput.name)
    async def campaign_name(message: Message, state: FSMContext) -> None:
        if message.text == BTN_CANCEL:
            await state.clear()
            await send_scene(message, "start", "❌ Создание кампании отменено.", MAIN_MENU)
            return
        if not message.text:
            await send_scene(message, "campaign", "✍️ Пришли название обычным текстом.", CANCEL_MENU)
            return
        await state.clear()
        await create_campaign(message, message.text)

    @router.message(F.text == BTN_CHARACTER)
    async def character_button(message: Message) -> None:
        await show_character(message)

    @router.callback_query(F.data == "character:new")
    async def new_character(callback: CallbackQuery) -> None:
        await callback.answer()
        await create_character(callback.message)

    @router.callback_query(F.data == "character:show")
    async def current_character(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_character(callback.message)

    @router.message(F.text == BTN_QUEST)
    async def quest_button(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        quest = generate_quest(campaign["name"] if campaign else None)
        text = (
            "📜 <b>Новая нить судьбы</b>\n\n"
            f"Заказчик: {esc(quest['giver'])}\nЦель: <b>{esc(quest['goal'])}</b>\n"
            f"Награда: {esc(quest['reward'])}\nОсложнение: <i>{esc(quest['complication'])}</i>"
        )
        await store.log(message.chat.id, "quest", f"Квест: {quest['goal']}; награда: {quest['reward']}", payload=quest)
        await send_scene(message, "quest", text + suffix, MAIN_MENU)

    @router.message(F.text == BTN_NPC)
    async def npc_button(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        npc = generate_npc(campaign["name"] if campaign else None)
        text = (
            f"🎭 <b>{esc(npc['name'])}</b>\n\nВнешность: {esc(npc['appearance'])}\n"
            f"Характер: {esc(npc['trait'])}\nОтношение: {esc(npc['attitude'])}\n"
            f"Секрет мастера: <tg-spoiler>{esc(npc['secret'])}</tg-spoiler>"
        )
        await store.log(message.chat.id, "npc", f"Встречен NPC {npc['name']}: {npc['trait']}", payload=npc)
        await send_scene(message, "npc", text + suffix, MAIN_MENU)

    @router.message(F.text == BTN_ENCOUNTER)
    async def encounter_button(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        encounter = generate_encounter(campaign["name"] if campaign else None)
        icon = {"дружелюбная": "🕊️", "нейтральная": "🌫️", "враждебная": "⚔️"}[encounter["kind"]]
        scene = {"дружелюбная": "encounter_friendly", "нейтральная": "encounter_neutral", "враждебная": "encounter_hostile"}[encounter["kind"]]
        text = f"{icon} <b>{esc(encounter['kind'].title())} встреча</b>\n\n{esc(encounter['description'])}"
        await store.log(message.chat.id, "encounter", f"{encounter['kind'].title()} встреча: {encounter['description']}", payload=encounter)
        await send_scene(message, scene, text + suffix, MAIN_MENU)

    @router.message(F.text == BTN_LOOT)
    async def loot_button(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        loot = generate_loot(campaign["name"] if campaign else None)
        icon = {"обычная": "⚪", "редкая": "🔵", "эпическая": "🟣", "легендарная": "🟠"}[loot["rarity"]]
        scene = "loot_common" if loot["rarity"] == "обычная" else "loot_rare"
        text = f"💎 <b>Добыча найдена</b>\n\n{icon} Редкость: {esc(loot['rarity'])}\nПредмет: <b>{esc(loot['item'])}</b>"
        await store.log(message.chat.id, "loot", f"{loot['rarity'].title()} добыча: {loot['item']}", payload=loot)
        await send_scene(message, scene, text + suffix, MAIN_MENU)

    @router.message(F.text == BTN_DICE)
    async def dice_button(message: Message) -> None:
        await send_scene(message, "attack", "🎲 <b>Выбери кость для броска.</b>", DICE_MENU)

    @router.callback_query(F.data.startswith("dice:"))
    async def dice_callback(callback: CallbackQuery) -> None:
        await callback.answer("Кости брошены!")
        await roll_dice(callback.message, callback.data.split(":", 1)[1])

    return router
