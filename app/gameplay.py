from __future__ import annotations

import random
from typing import Any

SHOP_ITEMS: tuple[dict[str, Any], ...] = (
    {"name": "Зелье лечения", "price": 25, "rarity": "обычная", "description": "восстанавливает 1d8+2 HP"},
    {"name": "Большое зелье лечения", "price": 75, "rarity": "редкая", "description": "восстанавливает 2d8+4 HP"},
    {"name": "Противоядие", "price": 30, "rarity": "обычная", "description": "снимает действие обычного яда"},
    {"name": "Свиток щита", "price": 60, "rarity": "редкая", "description": "даёт +2 КД в следующем бою"},
    {"name": "Серебряные стрелы", "price": 45, "rarity": "редкая", "description": "боеприпасы против нечисти"},
    {"name": "Перо феникса", "price": 180, "rarity": "эпическая", "description": "редкий компонент возвращения к жизни"},
)

CONSUMABLES: dict[str, tuple[int, int, int]] = {
    "Зелье лечения": (1, 8, 2),
    "Большое зелье лечения": (2, 8, 4),
}


def get_shop_item(index: int) -> dict[str, Any]:
    if index < 0 or index >= len(SHOP_ITEMS):
        raise ValueError("Товар не найден")
    return dict(SHOP_ITEMS[index])


def calculate_party_level(members: list[dict[str, Any]], fallback: int = 1) -> int:
    levels = [int(member.get("character", {}).get("level", 1)) for member in members]
    if not levels:
        return max(1, int(fallback))
    return max(1, round(sum(levels) / len(levels)))


def use_healing_item(
    character: dict[str, Any], item_name: str, rng: random.Random | None = None
) -> dict[str, int]:
    if item_name not in CONSUMABLES:
        raise ValueError("Этот предмет нельзя использовать как лечебное зелье")
    roller = rng or random
    count, sides, bonus = CONSUMABLES[item_name]
    rolled = sum(roller.randint(1, sides) for _ in range(count)) + bonus
    before = int(character["current_hp"])
    maximum = int(character["max_hp"])
    character["current_hp"] = min(maximum, before + rolled)
    return {"rolled": rolled, "restored": int(character["current_hp"]) - before}
