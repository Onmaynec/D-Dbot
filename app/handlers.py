from __future__ import annotations

import html
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.combat import attack, cast_spell, living_enemies, start_combat
from app.database import Database
from app.dice import ability_modifier, format_modifier, parse_and_roll
from app.generators import (
    generate_campaign,
    generate_character,
    generate_encounter,
    generate_loot,
    generate_npc,
    generate_quest,
    generate_rest_event,
    generate_spell,
)
from app.session import SessionStore

EVENT_ICONS = {
    "roll": "🎲", "character": "🧙", "quest": "📜", "campaign": "🌍", "npc": "🎭",
    "encounter": "⚔️", "loot": "💎", "combat": "🩸", "attack": "🗡️", "spell": "✨",
    "rest": "🔥", "levelup": "⬆️",
}


def esc(value: Any) -> str:
    return html.escape(str(value))


def signed(value: int) -> str:
    return format_modifier(value)


async def campaign_context(store: SessionStore, chat_id: int) -> tuple[dict[str, Any] | None, str]:
    campaign = await store.get_campaign(chat_id)
    if campaign:
        return campaign, f"\n\n<i>Кампания: {esc(campaign['name'])}</i>"
    return None, "\n\n<i>Кампания ещё не начата — используй /campaign название.</i>"


def character_text(character: dict[str, Any]) -> str:
    abilities = " · ".join(
        f"<b>{key}</b> {value} ({signed(ability_modifier(value))})"
        for key, value in character["abilities"].items()
    )
    return (
        f"🧙 <b>{esc(character['name'])}</b>\n"
        f"Раса: {esc(character['race'])}\n"
        f"Класс: {esc(character['class'])}\n"
        f"Предыстория: {esc(character['background'])}\n"
        f"Уровень: {character['level']} · XP: {character['xp']}\n"
        f"Хиты: {character['current_hp']}/{character['max_hp']}\n\n"
        f"{abilities}"
    )


def enemies_text(state: dict[str, Any]) -> str:
    lines = []
    for enemy in state["enemies"]:
        status = f"{enemy['hp']}/{enemy['max_hp']} HP" if enemy.get("alive", True) else "повержен"
        lines.append(f"{enemy['id']}. <b>{esc(enemy['name'])}</b> — КД {enemy['ac']}, {status}")
    return "\n".join(lines)


def build_router(database: Database, store: SessionStore) -> Router:
    router = Router(name=__name__)

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        await message.answer(
            "🐉 <b>Врата подземелья открыты.</b>\n\n"
            "Я стану летописцем, судьёй кубов и голосом мира. Начни с "
            "<code>/campaign Пепельная Корона</code>, создай героя через /character — и шагни во тьму.\n\n"
            "Полный список заклинаний-команд: /help"
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await message.answer(
            "📖 <b>Гримуар команд</b>\n\n"
            "<b>Приключение</b>\n"
            "/campaign [название] — создать мир и начать кампанию\n"
            "/character — создать случайного героя\n"
            "/quest — получить квест\n"
            "/npc — встретить NPC\n"
            "/encounter — случайная встреча\n"
            "/loot — найти добычу\n\n"
            "<b>Кубы и бой</b>\n"
            "/roll d20 — бросить кубик; поддерживаются d4–d100\n"
            "/combat — начать бой\n"
            "/attack [номер или имя] — атаковать цель\n"
            "/spell [название] — сотворить заклинание\n"
            "/rest — восстановить хиты и пережить ночное событие\n"
            "/levelup — проверить повышение уровня\n\n"
            "<b>Летопись</b>\n"
            "/journal — последние события\n"
            "/export — скачать журнал в TXT"
        )

    @router.message(Command("campaign"))
    async def campaign_handler(message: Message, command: CommandObject) -> None:
        campaign = generate_campaign(command.args)
        await store.set_campaign(message.chat.id, campaign)
        factions = "\n".join(f"• {esc(name)}" for name in campaign["factions"])
        text = (
            f"🌍 <b>Начинается кампания «{esc(campaign['name'])}»</b>\n\n"
            f"Мир: <b>{esc(campaign['world_name'])}</b>\n"
            f"Жанр: {esc(campaign['world_type'])}\n\n"
            f"<b>Три силы уже делят судьбу мира:</b>\n{factions}\n\n"
            "Где-то вдали гремит первый гром. История ждёт своих героев."
        )
        await store.log(message.chat.id, "campaign", text.replace("<b>", "").replace("</b>", ""))
        await message.answer(text)

    @router.message(Command("roll"))
    async def roll_handler(message: Message, command: CommandObject) -> None:
        notation = command.args or "d20"
        try:
            result = parse_and_roll(notation)
        except ValueError as error:
            await message.answer(f"⚠️ {esc(error)}")
            return
        rolls = ", ".join(map(str, result.rolls))
        modifier = f" {signed(result.modifier)}" if result.modifier else ""
        text = (
            f"🎲 <b>Кости ударяются о стол…</b>\n"
            f"<code>{esc(result.notation)}</code>: [{rolls}]{modifier} = <b>{result.total}</b>"
        )
        _, suffix = await campaign_context(store, message.chat.id)
        await store.log(
            message.chat.id,
            "roll",
            f"{result.notation}: {result.total} ({rolls})",
            payload={"notation": result.notation, "rolls": list(result.rolls), "modifier": result.modifier, "total": result.total},
        )
        await message.answer(text + suffix)

    @router.message(Command("character"))
    async def character_handler(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        character = generate_character()
        character_id = await database.add_character(
            message.chat.id,
            campaign["name"] if campaign else None,
            character,
        )
        character["id"] = character_id
        text = character_text(character)
        await store.log(
            message.chat.id,
            "character",
            f"Создан персонаж: {character['name']}, {character['race']} {character['class']}",
            payload=character,
        )
        await message.answer(text + suffix)

    @router.message(Command("quest"))
    async def quest_handler(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        quest = generate_quest(campaign["name"] if campaign else None)
        text = (
            f"📜 <b>Новая нить судьбы</b>\n\n"
            f"Заказчик: {esc(quest['giver'])}\n"
            f"Цель: <b>{esc(quest['goal'])}</b>\n"
            f"Награда: {esc(quest['reward'])}\n"
            f"Осложнение: <i>{esc(quest['complication'])}</i>"
        )
        await store.log(
            message.chat.id,
            "quest",
            f"Квест: {quest['goal']}; награда: {quest['reward']}; осложнение: {quest['complication']}",
            payload=quest,
        )
        await message.answer(text + suffix)

    @router.message(Command("npc"))
    async def npc_handler(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        npc = generate_npc(campaign["name"] if campaign else None)
        text = (
            f"🎭 <b>{esc(npc['name'])}</b>\n\n"
            f"Внешность: {esc(npc['appearance'])}\n"
            f"Характер: {esc(npc['trait'])}\n"
            f"Отношение к героям: {esc(npc['attitude'])}\n"
            f"Секрет мастера: <tg-spoiler>{esc(npc['secret'])}</tg-spoiler>"
        )
        await store.log(message.chat.id, "npc", f"Встречен NPC {npc['name']}: {npc['trait']}; секрет — {npc['secret']}")
        await message.answer(text + suffix)

    @router.message(Command("encounter"))
    async def encounter_handler(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        encounter = generate_encounter(campaign["name"] if campaign else None)
        icon = {"дружелюбная": "🕊️", "нейтральная": "🌫️", "враждебная": "⚔️"}[encounter["kind"]]
        text = f"{icon} <b>{esc(encounter['kind'].title())} встреча</b>\n\n{esc(encounter['description'])}"
        await store.log(message.chat.id, "encounter", f"{encounter['kind'].title()} встреча: {encounter['description']}")
        await message.answer(text + suffix)

    @router.message(Command("loot"))
    async def loot_handler(message: Message) -> None:
        campaign, suffix = await campaign_context(store, message.chat.id)
        loot = generate_loot(campaign["name"] if campaign else None)
        rarity_icon = {"обычная": "⚪", "редкая": "🔵", "эпическая": "🟣", "легендарная": "🟠"}[loot["rarity"]]
        text = f"💎 <b>Добыча найдена</b>\n\n{rarity_icon} Редкость: {esc(loot['rarity'])}\nПредмет: <b>{esc(loot['item'])}</b>"
        await store.log(message.chat.id, "loot", f"{loot['rarity'].title()} добыча: {loot['item']}")
        await message.answer(text + suffix)

    @router.message(Command("combat"))
    async def combat_handler(message: Message) -> None:
        character = await database.get_active_character(message.chat.id)
        level = int(character["level"]) if character else 1
        state = start_combat(level)
        await store.set_combat(message.chat.id, state)
        text = (
            f"🩸 <b>Инициатива брошена. Бой начинается!</b>\n\n"
            f"Уровень угрозы: {level}\n{enemies_text(state)}\n\n"
            "Атакуй командой <code>/attack 1</code> или сотвори <code>/spell огненный шар</code>."
        )
        await store.log(message.chat.id, "combat", f"Начат бой: {', '.join(enemy['name'] for enemy in state['enemies'])}")
        _, suffix = await campaign_context(store, message.chat.id)
        await message.answer(text + suffix)

    @router.message(Command("attack"))
    async def attack_handler(message: Message, command: CommandObject) -> None:
        state = await store.get_combat(message.chat.id)
        if not state:
            await message.answer("🛡️ Сейчас нет активного боя. Используй /combat.")
            return
        target_text = command.args or "1"
        character = await database.get_active_character(message.chat.id)
        strength = character["abilities"]["СИЛ"] if character else 16
        modifier = ability_modifier(strength)
        proficiency = 2 + max(0, ((character or {}).get("level", 1) - 1) // 4)
        try:
            result = attack(state, target_text, modifier + proficiency, modifier)
        except ValueError as error:
            await message.answer(f"⚠️ {esc(error)}\n\n{enemies_text(state)}")
            return

        target = result["target"]
        if result["critical"]:
            outcome = f"💥 <b>КРИТИЧЕСКИЙ УДАР!</b> {result['damage']} урона."
        elif result["hit"]:
            outcome = f"🗡️ Попадание: <b>{result['damage']} урона</b>."
        else:
            outcome = "🛡️ Удар встречает броню — промах."
        text = (
            f"🎲 d20: {result['natural']} {signed(modifier + proficiency)} = <b>{result['total']}</b> против КД {target['ac']}\n"
            f"{outcome}\n"
            f"{esc(target['name'])}: {target['hp']}/{target['max_hp']} HP"
        )

        if result["defeated"] and character:
            character["xp"] += result["xp"]
            await database.update_character(character)
            text += f"\n☠️ Противник повержен. Получено <b>{result['xp']} XP</b>."

        if living_enemies(state):
            await store.set_combat(message.chat.id, state)
        else:
            await store.clear_combat(message.chat.id)
            text += "\n\n🏆 <b>Поле боя стихает. Победа!</b>"

        await store.log(message.chat.id, "attack", f"Атака по {target['name']}: бросок {result['total']}, урон {result['damage']}")
        _, suffix = await campaign_context(store, message.chat.id)
        await message.answer(text + suffix)

    @router.message(Command("spell"))
    async def spell_handler(message: Message, command: CommandObject) -> None:
        if not command.args:
            await message.answer("✨ Назови заклинание: <code>/spell ледяное копьё</code>")
            return
        spell = generate_spell(command.args)
        state = await store.get_combat(message.chat.id)
        character = await database.get_active_character(message.chat.id)
        wisdom = character["abilities"]["МДР"] if character else 16
        modifier = ability_modifier(wisdom) + 2
        intro = (
            f"✨ <b>{esc(spell['name'])}</b> — школа: {esc(spell['school'])}\n"
            f"{esc(spell['visual'])}. Требуется {esc(spell['save'])}."
        )
        if not state:
            await store.log(message.chat.id, "spell", f"Сотворено {spell['name']} вне боя: {spell['visual']}")
            _, suffix = await campaign_context(store, message.chat.id)
            await message.answer(intro + "\n\nМагия отвечает эхом, но рядом нет цели." + suffix)
            return
        result = cast_spell(state, spell, modifier)
        target = result["target"]
        if result["success"]:
            outcome = f"Заклинание поражает {esc(target['name'])}: <b>{result['damage']} урона</b>."
        else:
            outcome = f"{esc(target['name'])} выдерживает натиск магии."
        text = f"{intro}\n\n🎲 d20: {result['natural']} {signed(modifier)} = <b>{result['total']}</b>\n{outcome}"
        if result["defeated"] and character:
            character["xp"] += result["xp"]
            await database.update_character(character)
            text += f"\n☠️ Цель повержена. Получено <b>{result['xp']} XP</b>."
        if living_enemies(state):
            await store.set_combat(message.chat.id, state)
        else:
            await store.clear_combat(message.chat.id)
            text += "\n\n🏆 <b>Последний враг пал.</b>"
        await store.log(message.chat.id, "spell", f"{spell['name']}: бросок {result['total']}, урон {result['damage']}")
        _, suffix = await campaign_context(store, message.chat.id)
        await message.answer(text + suffix)

    @router.message(Command("rest"))
    async def rest_handler(message: Message) -> None:
        character = await database.get_active_character(message.chat.id)
        healing = "Герои отдыхают, собирая силы."
        if character:
            before = character["current_hp"]
            character["current_hp"] = character["max_hp"]
            await database.update_character(character)
            healing = f"{esc(character['name'])} восстанавливает {character['max_hp'] - before} HP ({character['max_hp']}/{character['max_hp']})."
        event = generate_rest_event()
        text = f"🔥 <b>Долгий отдых</b>\n\n{healing}\n\n<i>{esc(event)}</i>"
        await store.log(message.chat.id, "rest", f"Отдых: {event}")
        _, suffix = await campaign_context(store, message.chat.id)
        await message.answer(text + suffix)

    @router.message(Command("levelup"))
    async def levelup_handler(message: Message) -> None:
        character = await database.get_active_character(message.chat.id)
        if not character:
            await message.answer("🧙 Сначала создай персонажа командой /character.")
            return
        required = character["level"] * 100
        if character["xp"] < required:
            await message.answer(
                f"⌛ <b>{esc(character['name'])}</b> ещё не готов к новому уровню.\n"
                f"Опыт: {character['xp']}/{required} XP."
            )
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="💪 Сила", callback_data=f"lvl:{character['id']}:str"),
                    InlineKeyboardButton(text="🏹 Ловкость", callback_data=f"lvl:{character['id']}:dex"),
                ],
                [
                    InlineKeyboardButton(text="🔮 Мудрость", callback_data=f"lvl:{character['id']}:wis"),
                    InlineKeyboardButton(text="❤️ Живучесть", callback_data=f"lvl:{character['id']}:vit"),
                ],
            ]
        )
        await message.answer(
            f"⬆️ <b>{esc(character['name'])} достигает {character['level'] + 1} уровня!</b>\n"
            "Выбери путь развития:",
            reply_markup=keyboard,
        )

    @router.callback_query(F.data.startswith("lvl:"))
    async def levelup_callback(callback: CallbackQuery) -> None:
        if not callback.data or not callback.message:
            return
        _, raw_id, choice = callback.data.split(":", 2)
        character = await database.get_active_character(callback.message.chat.id)
        if not character or character["id"] != int(raw_id):
            await callback.answer("Этот герой больше не активен.", show_alert=True)
            return
        required = character["level"] * 100
        if character["xp"] < required:
            await callback.answer("Недостаточно опыта.", show_alert=True)
            return
        labels = {"str": "СИЛ", "dex": "ЛОВ", "wis": "МДР"}
        character["xp"] -= required
        character["level"] += 1
        if choice in labels:
            stat = labels[choice]
            character["abilities"][stat] += 1
            change = f"{stat} повышена до {character['abilities'][stat]}"
        else:
            character["max_hp"] += 5
            character["current_hp"] = character["max_hp"]
            change = f"максимум хитов повышен до {character['max_hp']}"
        await database.update_character(character)
        await store.log(callback.message.chat.id, "levelup", f"{character['name']} получил {character['level']} уровень: {change}")
        await callback.message.edit_text(
            f"⬆️ <b>{esc(character['name'])} теперь {character['level']} уровня.</b>\n{esc(change.capitalize())}."
        )
        await callback.answer("Путь избран!")

    @router.message(Command("journal"))
    async def journal_handler(message: Message) -> None:
        entries = await store.get_journal(message.chat.id, limit=20)
        if not entries:
            await message.answer("📖 Страницы журнала пока пусты.")
            return
        lines = []
        for index, entry in enumerate(entries, start=1):
            icon = EVENT_ICONS.get(entry["event_type"], "•")
            lines.append(f"{index}. {icon} {esc(entry['content'])}")
        campaign = await store.get_campaign(message.chat.id)
        title = f"Журнал кампании «{esc(campaign['name'])}»" if campaign else "Журнал текущей сессии"
        await message.answer(f"📖 <b>{title}</b>\n\n" + "\n".join(lines))

    @router.message(Command("export"))
    async def export_handler(message: Message) -> None:
        entries = await database.get_journal(message.chat.id, limit=10_000)
        campaign = await store.get_campaign(message.chat.id)
        title = campaign["name"] if campaign else "Безымянная сессия"
        lines = [f"ЖУРНАЛ КАМПАНИИ: {title}", "=" * 60, ""]
        for entry in entries:
            date = entry["created_at"].replace("T", " ")
            lines.append(f"[{date}] {entry['event_type'].upper()}: {entry['content']}")
        if not entries:
            lines.append("Журнал пока пуст.")
        payload = "\n".join(lines).encode("utf-8")
        document = BufferedInputFile(payload, filename="dnd_journal.txt")
        await message.answer_document(document, caption="📜 Летопись кампании сохранена в TXT.")

    return router
