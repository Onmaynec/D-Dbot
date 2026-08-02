from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.button_ui.common import esc
from app.button_ui.keyboards import COMBAT_MENU, attack_targets_keyboard
from app.button_ui.media import send_scene
from app.combat import living_enemies
from app.database import Database
from app.party_combat import action_guard, party_member, pending_members
from app.party_support import HEALING_ITEMS_BY_CODE, PartySupportStore
from app.session import SessionStore

ITEM_LABELS = {
    "small": "Зелье лечения",
    "greater": "Большое зелье лечения",
}


def _inventory_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        str(item["item_name"]): int(item["quantity"])
        for item in items
    }


def _support_keyboard(
    state: dict[str, Any],
    items: list[dict[str, Any]],
) -> InlineKeyboardMarkup:
    counts = _inventory_counts(items)
    rows: list[list[InlineKeyboardButton]] = []

    for member in state.get("party", []):
        character = member.get("character", {})
        current_hp = int(character.get("current_hp", 0))
        max_hp = int(character.get("max_hp", 1))
        if current_hp >= max_hp:
            continue
        user_id = int(member["user_id"])
        target_name = str(character.get("name", member.get("display_name", "Герой")))
        if counts.get(ITEM_LABELS["small"], 0) > 0:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"🧪 {target_name}: малое зелье",
                        callback_data=f"support:heal:small:{user_id}",
                    )
                ]
            )
        if counts.get(ITEM_LABELS["greater"], 0) > 0:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"💖 {target_name}: большое зелье",
                        callback_data=f"support:heal:greater:{user_id}",
                    )
                ]
            )

    rows.extend(
        [
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="support:show")],
            [InlineKeyboardButton(text="⚔️ Вернуться к бою", callback_data="combat:status")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _party_lines(state: dict[str, Any]) -> str:
    acted = {int(value) for value in state.get("acted_user_ids", [])}
    lines: list[str] = []
    for member in state.get("party", []):
        user_id = int(member["user_id"])
        character = member["character"]
        current_hp = int(character["current_hp"])
        max_hp = int(character["max_hp"])
        if current_hp <= 0:
            marker = "💀"
            turn = "без сознания"
        elif user_id in acted:
            marker = "✅"
            turn = "ход завершён"
        else:
            marker = "⏳"
            turn = "ожидает ход"
        lines.append(
            f"{marker} <b>{esc(character['name'])}</b>: "
            f"{current_hp}/{max_hp} HP · {turn}"
        )
    return "\n".join(lines)


def _enemy_phase_text(events: tuple[dict[str, Any], ...]) -> str:
    if not events:
        return ""
    lines = ["\n\n<b>Ход врагов</b>"]
    for event in events:
        enemy = esc(event["enemy"])
        target = esc(event["target_name"])
        if event["critical"]:
            line = (
                f"💥 {enemy} наносит критический удар по {target}: "
                f"{event['damage']} урона"
            )
        elif event["hit"]:
            line = (
                f"🩸 {enemy} атакует {target}: "
                f"{event['damage']} урона"
            )
        else:
            line = f"🛡️ {enemy} промахивается по {target}"
        line += f" · HP {event['current_hp']}/{event['max_hp']}"
        if event["revived"]:
            line += " · 🔥 Перо феникса возвращает героя"
        lines.append(line)
    return "\n".join(lines)


def build_support_router(
    database: Database,
    store: SessionStore,
    support_store: PartySupportStore,
) -> Router:
    router = Router(name="button_party_support")

    async def show_support(
        message: Message,
        actor_user_id: int,
        notice: str = "",
    ) -> None:
        state = await store.get_combat(message.chat.id)
        if (
            not state
            or not bool(state.get("party_mode", False))
            or not living_enemies(state)
        ):
            await send_scene(
                message,
                "combat",
                "🤝 <b>Поддержка доступна только во время партийного боя.</b>",
                COMBAT_MENU,
            )
            return

        actor = party_member(state, actor_user_id)
        if actor is None:
            await send_scene(
                message,
                "combat",
                "👥 Сначала вступи в партию, чтобы помогать союзникам.",
                attack_targets_keyboard(state),
            )
            return

        items = await database.get_inventory(message.chat.id)
        counts = _inventory_counts(items)
        reason = action_guard(state, actor_user_id)
        wounded = [
            member
            for member in state.get("party", [])
            if int(member["character"]["current_hp"])
            < int(member["character"]["max_hp"])
        ]
        prefix = f"{notice}\n\n" if notice else ""
        availability = (
            f"🧪 Малые зелья: <b>{counts.get(ITEM_LABELS['small'], 0)}</b>\n"
            f"💖 Большие зелья: <b>{counts.get(ITEM_LABELS['greater'], 0)}</b>"
        )
        if reason:
            instruction = f"⚠️ {esc(reason)}"
        elif not wounded:
            instruction = "✅ Все герои полностью здоровы."
        elif not any(counts.get(name, 0) for name in ITEM_LABELS.values()):
            instruction = "🎒 В общем инвентаре нет лечебных зелий."
        else:
            instruction = (
                "Выбери союзника и зелье. Лечение тратит твой ход, "
                "но может вернуть героя из бессознательного состояния."
            )

        await send_scene(
            message,
            "rest",
            prefix
            + "🤝 <b>Полевая поддержка</b>\n\n"
            + availability
            + "\n\n"
            + _party_lines(state)
            + "\n\n"
            + instruction,
            _support_keyboard(state, items),
        )

    @router.message(Command("support"))
    async def support_command(message: Message) -> None:
        if message.from_user is None:
            return
        await show_support(message, message.from_user.id)

    @router.callback_query(F.data == "support:show")
    async def support_show(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_support(callback.message, callback.from_user.id)

    @router.callback_query(F.data.startswith("support:heal:"))
    async def support_heal(callback: CallbackQuery) -> None:
        try:
            _, _, item_code, raw_target = callback.data.split(":", 3)
            target_user_id = int(raw_target)
        except (ValueError, AttributeError):
            await callback.answer("Кнопка поддержки устарела.", show_alert=True)
            return

        if item_code not in HEALING_ITEMS_BY_CODE:
            await callback.answer("Неизвестное зелье.", show_alert=True)
            return

        result = await support_store.heal(
            callback.message.chat.id,
            callback.from_user.id,
            target_user_id,
            item_code,
        )
        if not result.allowed or result.state is None:
            await callback.answer(result.reason, show_alert=True)
            await show_support(callback.message, callback.from_user.id)
            return

        if result.defeat:
            await store.clear_combat(callback.message.chat.id)
        else:
            await store.cache_combat(callback.message.chat.id, result.state)

        actor_name = esc(result.actor["character"]["name"])
        target_name = esc(result.target["character"]["name"])
        text = (
            f"🤝 <b>{actor_name} помогает союзнику</b>\n\n"
            f"🧪 {esc(result.item_name)} → {target_name}\n"
            f"❤️ Восстановлено: <b>{result.restored} HP</b> "
            f"(бросок {result.rolled})\n"
            f"🎒 Осталось предметов: <b>{result.remaining}</b>"
        )
        await store.log(
            callback.message.chat.id,
            "party_support",
            (
                f"{result.actor['display_name']} использует "
                f"{result.item_name} на {result.target['display_name']}: "
                f"+{result.restored} HP"
            ),
            payload={
                "item": result.item_name,
                "restored": result.restored,
                "target_user_id": target_user_id,
            },
        )

        if result.round_complete:
            text += _enemy_phase_text(result.enemy_events)
            if result.shield_expired:
                text += "\n⌛ Защитная руна гаснет."
            if result.defeat:
                text += "\n\n☠️ <b>Вся партия повержена.</b>"
            else:
                text += (
                    f"\n\n🔄 <b>Начинается раунд "
                    f"{result.state.get('round', 1)}.</b>"
                )
        else:
            waiting = pending_members(result.state)
            names = ", ".join(
                esc(member["character"]["name"])
                for member in waiting
            )
            text += f"\n\n⏳ Ожидаются ходы: {names or 'никого'}."

        await callback.answer("Союзнику оказана помощь!")
        keyboard = (
            COMBAT_MENU
            if result.defeat
            else attack_targets_keyboard(result.state)
        )
        await send_scene(callback.message, "rest", text, keyboard)

    return router
