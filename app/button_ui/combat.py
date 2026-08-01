from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.combat import attack, cast_spell, living_enemies, start_combat
from app.database import Database
from app.dice import ability_modifier, parse_and_roll
from app.generators import generate_rest_event, generate_spell
from app.session import SessionStore
from app.button_ui.common import campaign_context, enemies_text, esc, signed
from app.button_ui.keyboards import (
    BTN_CANCEL,
    BTN_COMBAT,
    BTN_MAGIC,
    BTN_REST,
    CANCEL_MENU,
    CHARACTER_MENU,
    COMBAT_MENU,
    MAIN_MENU,
    SPELL_MENU,
    attack_targets_keyboard,
    levelup_keyboard,
)
from app.button_ui.media import send_scene


class SpellInput(StatesGroup):
    name = State()


def build_combat_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_combat")

    async def show_combat(message: Message) -> None:
        state = await store.get_combat(message.chat.id)
        if not state or not living_enemies(state):
            await send_scene(
                message,
                "combat",
                "🛡️ <b>Сейчас нет активного боя.</b>\n\nНачни новую схватку кнопкой ниже.",
                COMBAT_MENU,
            )
            return
        await send_scene(
            message,
            "combat",
            f"🛡️ <b>Раунд {state.get('round', 1)}</b>\n\n{enemies_text(state)}\n\nВыбери цель атаки:",
            attack_targets_keyboard(state),
        )

    async def begin_combat(message: Message) -> None:
        character = await database.get_active_character(message.chat.id)
        level = int(character["level"]) if character else 1
        state = start_combat(level)
        await store.set_combat(message.chat.id, state)
        await store.log(
            message.chat.id,
            "combat",
            f"Начат бой: {', '.join(enemy['name'] for enemy in state['enemies'])}",
            payload=state,
        )
        _, suffix = await campaign_context(store, message.chat.id)
        await send_scene(
            message,
            "combat",
            f"🩸 <b>Инициатива брошена. Бой начинается!</b>\n\n"
            f"Уровень угрозы: {level}\n{enemies_text(state)}\n\nВыбери противника кнопкой ниже.{suffix}",
            attack_targets_keyboard(state),
        )

    async def choose_target(message: Message) -> None:
        state = await store.get_combat(message.chat.id)
        if not state or not living_enemies(state):
            await show_combat(message)
            return
        await send_scene(message, "attack", f"🗡️ <b>Кого атаковать?</b>\n\n{enemies_text(state)}", attack_targets_keyboard(state))

    async def perform_attack(message: Message, target_text: str) -> None:
        state = await store.get_combat(message.chat.id)
        if not state:
            await send_scene(message, "combat", "🛡️ Сейчас нет активного боя.", COMBAT_MENU)
            return
        character = await database.get_active_character(message.chat.id)
        strength = character["abilities"]["СИЛ"] if character else 16
        level = int(character["level"]) if character else 1
        modifier = ability_modifier(strength)
        proficiency = 2 + max(0, (level - 1) // 4)
        try:
            result = attack(state, target_text, modifier + proficiency, modifier)
        except ValueError as error:
            await send_scene(message, "attack", f"⚠️ {esc(error)}\n\n{enemies_text(state)}", attack_targets_keyboard(state))
            return

        target = result["target"]
        if result["critical"]:
            outcome = f"💥 <b>КРИТИЧЕСКИЙ УДАР!</b> {result['damage']} урона."
        elif result["hit"]:
            outcome = f"🗡️ Попадание: <b>{result['damage']} урона</b>."
        else:
            outcome = "🛡️ Удар встречает броню — промах."
        text = (
            f"🎲 d20: {result['natural']} {signed(modifier + proficiency)} = <b>{result['total']}</b> "
            f"против КД {target['ac']}\n{outcome}\n{esc(target['name'])}: {target['hp']}/{target['max_hp']} HP"
        )
        if result["defeated"] and character:
            character["xp"] += result["xp"]
            await database.update_character(character)
            text += f"\n☠️ Противник повержен. Получено <b>{result['xp']} XP</b>."
        if living_enemies(state):
            await store.set_combat(message.chat.id, state)
            keyboard = attack_targets_keyboard(state)
        else:
            await store.clear_combat(message.chat.id)
            text += "\n\n🏆 <b>Поле боя стихает. Победа!</b>"
            keyboard = COMBAT_MENU
        await store.log(
            message.chat.id,
            "attack",
            f"Атака по {target['name']}: бросок {result['total']}, урон {result['damage']}",
        )
        _, suffix = await campaign_context(store, message.chat.id)
        await send_scene(message, "attack", text + suffix, keyboard)

    async def cast_named_spell(message: Message, spell_name: str) -> None:
        spell_name = spell_name.strip()
        if not spell_name:
            await send_scene(message, "spell", "✨ Назови заклинание текстом.", SPELL_MENU)
            return
        spell = generate_spell(spell_name)
        state = await store.get_combat(message.chat.id)
        character = await database.get_active_character(message.chat.id)
        wisdom = character["abilities"]["МДР"] if character else 16
        level = int(character["level"]) if character else 1
        modifier = ability_modifier(wisdom) + 2 + max(0, (level - 1) // 4)
        text = (
            f"✨ <b>{esc(spell['name'])}</b>\nШкола: {esc(spell['school'])}\n"
            f"Эффект: {esc(spell['visual'])}\nПроверка: {esc(spell['save'])}"
        )
        keyboard = SPELL_MENU
        if state and living_enemies(state):
            result = cast_spell(state, spell, modifier)
            target = result["target"]
            if result["critical"]:
                outcome = f"💥 Магический крит: <b>{result['damage']} урона</b>."
            elif result["success"]:
                outcome = f"🔮 Заклинание достигает цели: <b>{result['damage']} урона</b>."
            else:
                outcome = "🌫️ Магия рассеивается, не пробив защиту цели."
            text += (
                f"\n\n🎲 d20: {result['natural']} {signed(modifier)} = <b>{result['total']}</b>\n"
                f"{outcome}\n{esc(target['name'])}: {target['hp']}/{target['max_hp']} HP"
            )
            if result["defeated"] and character:
                character["xp"] += result["xp"]
                await database.update_character(character)
                text += f"\n☠️ Получено <b>{result['xp']} XP</b>."
            if living_enemies(state):
                await store.set_combat(message.chat.id, state)
                keyboard = attack_targets_keyboard(state)
            else:
                await store.clear_combat(message.chat.id)
                text += "\n\n🏆 <b>Последний враг повержен магией!</b>"
                keyboard = COMBAT_MENU
        else:
            result = parse_and_roll(f"d20{signed(modifier)}")
            text += f"\n\n🎲 Проверка силы магии: <b>{result.total}</b>."
        await store.log(message.chat.id, "spell", f"Сотворено заклинание {spell['name']}", payload=spell)
        _, suffix = await campaign_context(store, message.chat.id)
        await send_scene(message, "spell", text + suffix, keyboard)

    async def check_levelup(message: Message) -> None:
        character = await database.get_active_character(message.chat.id)
        if not character:
            await send_scene(message, "levelup", "🧙 Сначала создай героя.", CHARACTER_MENU)
            return
        required = int(character["level"]) * 100
        if int(character["xp"]) < required:
            await send_scene(
                message,
                "levelup",
                f"⌛ <b>{esc(character['name'])}</b> ещё не готов к новому уровню.\n\n"
                f"Опыт: {character['xp']}/{required} XP.",
                CHARACTER_MENU,
            )
            return
        await send_scene(
            message,
            "levelup",
            f"⬆️ <b>{esc(character['name'])} достигает {character['level'] + 1} уровня!</b>\n\nВыбери путь развития:",
            levelup_keyboard(int(character["id"])),
        )

    @router.message(F.text == BTN_COMBAT)
    async def combat_button(message: Message) -> None:
        await show_combat(message)

    @router.callback_query(F.data == "combat:start")
    async def combat_start(callback: CallbackQuery) -> None:
        await callback.answer()
        await begin_combat(callback.message)

    @router.callback_query(F.data == "combat:status")
    async def combat_status(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_combat(callback.message)

    @router.callback_query(F.data == "combat:attack")
    async def combat_attack(callback: CallbackQuery) -> None:
        await callback.answer()
        await choose_target(callback.message)

    @router.callback_query(F.data.startswith("attack:"))
    async def attack_target(callback: CallbackQuery) -> None:
        await callback.answer("Атака!")
        await perform_attack(callback.message, callback.data.split(":", 1)[1])

    @router.message(F.text == BTN_MAGIC)
    async def magic_button(message: Message) -> None:
        await send_scene(message, "spell", "✨ <b>Выбери заклинание.</b>", SPELL_MENU)

    @router.callback_query(F.data == "combat:spell")
    async def combat_spell(callback: CallbackQuery) -> None:
        await callback.answer()
        await send_scene(callback.message, "spell", "✨ <b>Выбери боевое заклинание.</b>", SPELL_MENU)

    @router.callback_query(F.data.startswith("spell:"))
    async def spell_choice(callback: CallbackQuery, state: FSMContext) -> None:
        spell_name = callback.data.split(":", 1)[1]
        await callback.answer()
        if spell_name == "custom":
            await state.set_state(SpellInput.name)
            await send_scene(callback.message, "spell", "✍️ <b>Напиши название своего заклинания.</b>", CANCEL_MENU)
            return
        await cast_named_spell(callback.message, spell_name)

    @router.message(SpellInput.name)
    async def spell_name(message: Message, state: FSMContext) -> None:
        if message.text == BTN_CANCEL:
            await state.clear()
            await send_scene(message, "start", "❌ Создание заклинания отменено.", MAIN_MENU)
            return
        if not message.text:
            await send_scene(message, "spell", "✨ Пришли название обычным текстом.", CANCEL_MENU)
            return
        await state.clear()
        await cast_named_spell(message, message.text)

    @router.message(F.text == BTN_REST)
    async def rest_button(message: Message) -> None:
        state = await store.get_combat(message.chat.id)
        if state and living_enemies(state):
            await send_scene(message, "rest", "⚔️ <b>Отдых невозможен, пока рядом враги.</b>", COMBAT_MENU)
            return
        character = await database.get_active_character(message.chat.id)
        event = generate_rest_event()
        if character:
            restored = character["max_hp"] - character["current_hp"]
            character["current_hp"] = character["max_hp"]
            await database.update_character(character)
            recovery = f"❤️ {esc(character['name'])} восстанавливает {restored} HP."
        else:
            recovery = "🔥 У костра некому залечивать раны — сначала создай героя."
        await store.log(message.chat.id, "rest", f"Отдых: {event}")
        _, suffix = await campaign_context(store, message.chat.id)
        await send_scene(message, "rest", f"🛌 <b>Долгий отдых</b>\n\n{recovery}\n\n<i>{esc(event)}</i>{suffix}", MAIN_MENU)

    @router.callback_query(F.data == "levelup:check")
    async def levelup_check(callback: CallbackQuery) -> None:
        await callback.answer()
        await check_levelup(callback.message)

    @router.callback_query(F.data.startswith("lvl:"))
    async def levelup_apply(callback: CallbackQuery) -> None:
        _, raw_id, choice = callback.data.split(":", 2)
        character = await database.get_active_character(callback.message.chat.id)
        if not character or int(character["id"]) != int(raw_id):
            await callback.answer("Этот герой больше не активен.", show_alert=True)
            return
        required = int(character["level"]) * 100
        if int(character["xp"]) < required:
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
        await callback.answer("Путь избран!")
        await send_scene(
            callback.message,
            "levelup",
            f"⬆️ <b>{esc(character['name'])} теперь {character['level']} уровня.</b>\n\n{esc(change.capitalize())}.",
            CHARACTER_MENU,
        )

    return router
