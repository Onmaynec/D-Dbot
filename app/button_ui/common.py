from __future__ import annotations

import html
from typing import Any

from app.dice import ability_modifier, format_modifier
from app.equipment import SLOT_NAMES, equipment_bonuses, equipped_item_names
from app.session import SessionStore

EVENT_ICONS = {
    "roll": "🎲",
    "character": "🧙",
    "quest": "📜",
    "campaign": "🌍",
    "npc": "🎭",
    "encounter": "⚔️",
    "loot": "💎",
    "combat": "🩸",
    "attack": "🗡️",
    "spell": "✨",
    "rest": "🔥",
    "levelup": "⬆️",
    "equipment": "🧰",
    "casino": "🎰",
    "choice": "🧭",
    "party_attack": "⚔️",
    "party_spell": "🔮",
    "party_support": "🤝",
}

RARITY_ICONS = {
    "обычная": "⚪",
    "редкая": "🔵",
    "эпическая": "🟣",
    "легендарная": "🟠",
}


def esc(value: Any) -> str:
    return html.escape(str(value))


def signed(value: int) -> str:
    return format_modifier(value)


def clean_html(value: str) -> str:
    for tag in ("b", "i", "code", "u"):
        value = value.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
    return value


def progress_bar(current: int, maximum: int, width: int = 10) -> str:
    maximum = max(1, int(maximum))
    current = max(0, min(maximum, int(current)))
    filled = round(width * current / maximum)
    return "█" * filled + "░" * (width - filled)


def hp_line(current: int, maximum: int) -> str:
    return f"{progress_bar(current, maximum)}  <b>{current}/{maximum}</b> HP"


def rarity_icon(rarity: str) -> str:
    return RARITY_ICONS.get(str(rarity).lower(), "⚪")


def card_title(icon: str, title: str, subtitle: str | None = None) -> str:
    text = f"{icon} <b>{esc(title)}</b>"
    if subtitle:
        text += f"\n<i>{esc(subtitle)}</i>"
    return text


def divider() -> str:
    return "━━━━━━━━━━━━━━"


async def campaign_context(
    store: SessionStore,
    chat_id: int,
) -> tuple[dict[str, Any] | None, str]:
    campaign = await store.get_campaign(chat_id)
    if campaign:
        return campaign, f"\n\n🌍 <i>{esc(campaign['name'])}</i>"
    return None, "\n\n⚠️ <i>Кампания не начата — открой «🏕️ Кампания».</i>"


def character_text(character: dict[str, Any]) -> str:
    abilities = "\n".join(
        f"• <b>{key}</b> {value}  <code>{signed(ability_modifier(value))}</code>"
        for key, value in character["abilities"].items()
    )
    equipped = equipped_item_names(character)
    equipment_lines = [
        f"• {SLOT_NAMES.get(slot, slot)}: <b>{esc(name)}</b>"
        for slot, name in equipped.items()
    ]
    if not equipment_lines:
        equipment_lines = ["• <i>Слоты пусты — открой /equipment</i>"]
    bonuses = equipment_bonuses(character)
    bonus_line = (
        f"Урон <b>+{bonuses['damage']}</b> · Магия <b>+{bonuses['spell_damage']}</b> · "
        f"КД <b>+{bonuses['armor']}</b>"
    )
    return (
        f"🧙 <b>{esc(character['name'])}</b> · уровень {character['level']}\n"
        f"{esc(character['race'])} · {esc(character['class'])}\n"
        f"{hp_line(int(character['current_hp']), int(character['max_hp']))}\n"
        f"⭐ XP: <b>{character['xp']}</b>\n\n"
        f"<b>Характеристики</b>\n{abilities}\n\n"
        f"<b>Экипировка</b>\n" + "\n".join(equipment_lines) + f"\n{bonus_line}"
    )


def enemies_text(state: dict[str, Any]) -> str:
    lines: list[str] = []
    for enemy in state.get("enemies", []):
        alive = enemy.get("alive", True) and int(enemy.get("hp", 0)) > 0
        if alive:
            hp = int(enemy["hp"])
            maximum = int(enemy["max_hp"])
            lines.append(
                f"<b>{enemy['id']}. {esc(enemy['name'])}</b> · КД {enemy['ac']}\n"
                f"{progress_bar(hp, maximum, 8)}  {hp}/{maximum} HP"
            )
        else:
            lines.append(f"☠️ <s>{esc(enemy['name'])}</s> — повержен")
    return "\n\n".join(lines)
