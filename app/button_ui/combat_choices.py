from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.button_ui.common import enemies_text, esc, hp_line, signed
from app.button_ui.keyboards import COMBAT_ACTIONS_MENU, COMBAT_MENU, attack_targets_keyboard
from app.button_ui.media import send_scene
from app.combat_choices import CombatChoiceResult, CombatChoiceStore
from app.database import Database
from app.dice import ability_modifier
from app.party_combat import pending_members
from app.session import SessionStore


def _power_targets_keyboard(state: dict) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"💥 {enemy['id']}. {enemy['name']} · {enemy['hp']} HP",
                callback_data=f"v5:power:{enemy['id']}",
            )
        ]
        for enemy in state.get("enemies", [])
        if enemy.get("alive", True) and int(enemy.get("hp", 0)) > 0
    ]
    rows.append([InlineKeyboardButton(text="↩️ Обычные действия", callback_data="v5:actions")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _enemy_events(result: CombatChoiceResult) -> str:
    if not result.enemy_events:
        return ""
    lines = ["", "<b>Фаза врагов</b>"]
    for event in result.enemy_events:
        if event["critical"]:
            outcome = f"критический удар · {event['damage']} урона"
        elif event["hit"]:
            outcome = f"попадание · {event['damage']} урона"
        else:
            outcome = "промах"
        guard = " · 🛡️ стойка" if event.get("guarded") else ""
        lines.append(
            f"• {esc(event['enemy'])} → <b>{esc(event['target_name'])}</b>: {outcome}{guard}\n"
            f"  {hp_line(int(event['current_hp']), int(event['max_hp']))}"
        )
        if event.get("revived"):
            lines.append("  🔥 Перо феникса возвращает героя в строй.")
    if result.shield_expired:
        lines.append("⌛ Защитная руна гаснет.")
    return "\n".join(lines)


def _party_status(state: dict) -> str:
    acted = {int(value) for value in state.get("acted_user_ids", [])}
    guarded = {int(value) for value in state.get("guard_user_ids", [])}
    lines: list[str] = []
    for member in state.get("party", []):
        user_id = int(member["user_id"])
        character = member["character"]
        hp = int(character.get("current_hp", 0))
        if hp <= 0:
            marker = "☠️"
        elif user_id in guarded:
            marker = "🛡️"
        elif user_id in acted:
            marker = "✅"
        else:
            marker = "⏳"
        lines.append(
            f"{marker} <b>{esc(member['display_name'])}</b> · {esc(character['name'])} · "
            f"{hp}/{character['max_hp']} HP"
        )
    return "\n".join(lines)


def _reward_text(result: CombatChoiceResult) -> str:
    reward = result.reward
    if reward is None:
        return ""
    return (
        "\n\n🏆 <b>Награда партии</b>\n"
        f"⭐ +{reward.xp_each} XP каждому\n"
        f"💰 +{reward.gold} золота\n"
        f"🎁 {esc(reward.item_name)} ×{reward.quantity}"
    )


def build_combat_choices_router(
    database: Database,
    session: SessionStore,
    store: CombatChoiceStore,
) -> Router:
    router = Router(name="button_combat_choices_v5")

    async def sync_result(message: Message, result: CombatChoiceResult) -> None:
        if result.victory or result.defeat:
            await session.clear_combat(message.chat.id)
        elif result.state is not None:
            await session.cache_combat(message.chat.id, result.state)

    async def show_actions(message: Message) -> None:
        state = await session.get_combat(message.chat.id)
        if not state or not state.get("party_mode"):
            await send_scene(
                message,
                "combat",
                "⚠️ <b>Тактические действия доступны только в активном партийном бою.</b>",
                COMBAT_MENU,
            )
            return
        text = (
            f"⚔️ <b>Тактика · раунд {state.get('round', 1)}</b>\n\n"
            "🗡️ <b>Обычная атака</b> — стабильный бросок без штрафов.\n"
            "💥 <b>Рискованный удар</b> — −2 к попаданию, но +4 к урону оружия.\n"
            "🛡️ <b>Защитная стойка</b> — тратит ход, даёт минимум +3 КД и снижает "
            "полученный урон во время следующей фазы врагов.\n"
            "✨ <b>Магия</b> — урон усиливается экипированными посохами и талисманами.\n"
            "🤝 <b>Поддержка</b> — лечит союзника через /support.\n\n"
            f"<b>Противники</b>\n{enemies_text(state)}"
        )
        await send_scene(message, "combat", text, COMBAT_ACTIONS_MENU)

    @router.message(Command("actions"))
    async def actions_command(message: Message) -> None:
        await show_actions(message)

    @router.callback_query(F.data == "v5:actions")
    async def actions_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_actions(callback.message)

    @router.callback_query(F.data == "v5:power:menu")
    async def power_menu(callback: CallbackQuery) -> None:
        state = await session.get_combat(callback.message.chat.id)
        if not state or not state.get("party_mode"):
            await callback.answer("Партийный бой не найден.", show_alert=True)
            return
        await callback.answer()
        await send_scene(
            callback.message,
            "attack",
            "💥 <b>Рискованный удар</b>\n\n"
            "Штраф <b>−2 к попаданию</b>, бонус <b>+4 к урону</b> поверх оружия. "
            "Выбери цель:",
            _power_targets_keyboard(state),
        )

    @router.callback_query(F.data == "v5:guard")
    async def guard_action(callback: CallbackQuery) -> None:
        result = await store.guard(callback.message.chat.id, callback.from_user.id)
        if not result.ok or result.actor is None or result.action is None:
            await callback.answer(result.reason, show_alert=True)
            return
        await callback.answer("Защитная стойка принята")
        await sync_result(callback.message, result)
        actor = result.actor["character"]
        text = (
            f"🛡️ <b>{esc(result.actor['display_name'])}</b> закрывает строй героем "
            f"<b>{esc(actor['name'])}</b>.\n\n"
            f"КД во время фазы врагов: <b>+{result.action['armor_bonus']}</b>. "
            "Первый полученный удар также ослабляется."
            f"{_enemy_events(result)}"
        )
        if result.defeat:
            text += "\n\n☠️ <b>Партия пала.</b>"
            keyboard = COMBAT_MENU
        else:
            assert result.state is not None
            pending = pending_members(result.state)
            if pending:
                text += "\n\n⏳ Ход ожидается от: " + ", ".join(
                    esc(member["display_name"]) for member in pending
                )
            elif result.round_complete:
                text += f"\n\n🔄 Начинается раунд <b>{result.state['round']}</b>."
            text += "\n\n<b>Партия</b>\n" + _party_status(result.state)
            keyboard = attack_targets_keyboard(result.state)
        await session.log(
            callback.message.chat.id,
            "combat_choice",
            f"{result.actor['display_name']} принимает защитную стойку",
        )
        await send_scene(callback.message, "combat", text, keyboard)

    @router.callback_query(F.data.startswith("v5:power:"))
    async def power_attack(callback: CallbackQuery) -> None:
        target = callback.data.rsplit(":", 1)[1]
        if target == "menu":
            return
        result = await store.power_attack(
            callback.message.chat.id,
            callback.from_user.id,
            target,
        )
        if not result.ok or result.actor is None or result.action is None:
            await callback.answer(result.reason, show_alert=True)
            return
        await callback.answer("Рискованный удар!")
        await sync_result(callback.message, result)
        action = result.action
        actor = result.actor["character"]
        strength = ability_modifier(int(actor["abilities"]["СИЛ"]))
        proficiency = 2 + max(0, (int(actor.get("level", 1)) - 1) // 4)
        attack_modifier = strength + proficiency - 2
        target_data = action["target"]
        if action["critical"]:
            outcome = f"💥 <b>Критический удар · {action['damage']} урона</b>"
        elif action["hit"]:
            outcome = f"🗡️ Попадание · <b>{action['damage']} урона</b>"
        else:
            outcome = "🌫️ Риск не оправдался — промах."
        text = (
            f"💥 <b>{esc(result.actor['display_name'])}</b> проводит рискованный удар\n"
            f"Герой: <b>{esc(actor['name'])}</b>\n\n"
            f"🎲 d20: {action['natural']} {signed(attack_modifier)} = <b>{action['total']}</b> "
            f"против КД {target_data['ac']}\n"
            f"{outcome}\n"
            f"{esc(target_data['name'])}: {target_data['hp']}/{target_data['max_hp']} HP"
        )
        if action.get("equipment_damage_bonus"):
            text += f"\n🧰 Оружие добавило +{action['equipment_damage_bonus']} урона."
        text += _enemy_events(result)
        if result.victory:
            text += "\n\n🏆 <b>Последний противник повержен!</b>"
            text += _reward_text(result)
            keyboard = COMBAT_MENU
        elif result.defeat:
            text += "\n\n☠️ <b>Партия пала.</b>"
            keyboard = COMBAT_MENU
        else:
            assert result.state is not None
            pending = pending_members(result.state)
            if pending:
                text += "\n\n⏳ Ход ожидается от: " + ", ".join(
                    esc(member["display_name"]) for member in pending
                )
            elif result.round_complete:
                text += f"\n\n🔄 Начинается раунд <b>{result.state['round']}</b>."
            text += "\n\n<b>Партия</b>\n" + _party_status(result.state)
            keyboard = attack_targets_keyboard(result.state)
        await session.log(
            callback.message.chat.id,
            "combat_choice",
            f"{result.actor['display_name']} проводит рискованный удар по {target_data['name']}",
        )
        await send_scene(callback.message, "attack", text, keyboard)

    return router
