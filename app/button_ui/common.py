from __future__ import annotations

import html
from typing import Any

from app.dice import ability_modifier, format_modifier
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


def clean_html(value: str) -> str:
    for tag in ("b", "i", "code"):
        value = value.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
    return value


async def campaign_context(store: SessionStore, chat_id: int) -> tuple[dict[str, Any] | None, str]:
    campaign = await store.get_campaign(chat_id)
    if campaign:
        return campaign, f"\n\n<i>Кампания: {esc(campaign['name'])}</i>"
    return None, "\n\n<i>Кампания ещё не начата — нажми «🏕️ Кампания».</i>"


def character_text(character: dict[str, Any]) -> str:
    abilities = " · ".join(
        f"<b>{key}</b> {value} ({signed(ability_modifier(value))})"
        for key, value in character["abilities"].items()
    )
    return (
        f"🧙 <b>{esc(character['name'])}</b>\nРаса: {esc(character['race'])}\n"
        f"Класс: {esc(character['class'])}\nПредыстория: {esc(character['background'])}\n"
        f"Уровень: {character['level']} · XP: {character['xp']}\n"
        f"Хиты: {character['current_hp']}/{character['max_hp']}\n\n{abilities}"
    )


def enemies_text(state: dict[str, Any]) -> str:
    lines = []
    for enemy in state.get("enemies", []):
        status = f"{enemy['hp']}/{enemy['max_hp']} HP" if enemy.get("alive", True) else "повержен"
        lines.append(f"{enemy['id']}. <b>{esc(enemy['name'])}</b> — КД {enemy['ac']}, {status}")
    return "\n".join(lines)
