from __future__ import annotations

import random
from typing import Any

ENEMIES = [
    {"name": "гоблин-разведчик", "min_level": 1, "hp": 7, "ac": 13, "xp": 25},
    {"name": "скелет-страж", "min_level": 1, "hp": 9, "ac": 13, "xp": 30},
    {"name": "культист Бездны", "min_level": 2, "hp": 14, "ac": 12, "xp": 45},
    {"name": "орк-налётчик", "min_level": 2, "hp": 18, "ac": 13, "xp": 55},
    {"name": "теневой волк", "min_level": 3, "hp": 22, "ac": 14, "xp": 70},
    {"name": "рыцарь-предатель", "min_level": 4, "hp": 32, "ac": 16, "xp": 110},
    {"name": "молодой мантикора", "min_level": 5, "hp": 46, "ac": 15, "xp": 160},
]


def start_combat(party_level: int, rng: random.Random | None = None) -> dict[str, Any]:
    roller = rng or random
    level = max(1, party_level)
    enemy_count = max(1, min(5, 1 + level // 2 + roller.choice([-1, 0, 0, 1])))
    pool = [enemy for enemy in ENEMIES if enemy["min_level"] <= level + 1]
    enemies: list[dict[str, Any]] = []
    for index in range(1, enemy_count + 1):
        template = dict(roller.choice(pool))
        scale = max(0, level - template["min_level"])
        template["id"] = index
        template["max_hp"] = template["hp"] + scale * 2
        template["hp"] = template["max_hp"]
        template["alive"] = True
        enemies.append(template)
    return {"round": 1, "party_level": level, "enemies": enemies}


def living_enemies(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [enemy for enemy in state.get("enemies", []) if enemy.get("alive", True) and enemy.get("hp", 0) > 0]


def resolve_target(state: dict[str, Any], target_text: str) -> dict[str, Any] | None:
    alive = living_enemies(state)
    target = target_text.strip().lower()
    if target.isdigit():
        target_id = int(target)
        return next((enemy for enemy in alive if enemy["id"] == target_id), None)
    return next((enemy for enemy in alive if target in enemy["name"].lower()), None)


def attack(
    state: dict[str, Any],
    target_text: str,
    attack_modifier: int,
    damage_modifier: int,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    roller = rng or random
    target = resolve_target(state, target_text)
    if target is None:
        raise ValueError("Цель не найдена среди живых противников")

    natural = roller.randint(1, 20)
    total = natural + attack_modifier
    critical = natural == 20
    hit = critical or (natural != 1 and total >= target["ac"])
    damage = 0
    defeated = False
    if hit:
        dice_count = 2 if critical else 1
        damage = sum(roller.randint(1, 8) for _ in range(dice_count)) + damage_modifier
        damage = max(1, damage)
        target["hp"] = max(0, target["hp"] - damage)
        if target["hp"] == 0:
            target["alive"] = False
            defeated = True

    state["round"] = state.get("round", 1) + 1
    return {
        "target": target,
        "natural": natural,
        "total": total,
        "hit": hit,
        "critical": critical,
        "damage": damage,
        "defeated": defeated,
        "xp": target["xp"] if defeated else 0,
    }


def cast_spell(
    state: dict[str, Any],
    spell: dict[str, Any],
    spell_modifier: int,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    roller = rng or random
    alive = living_enemies(state)
    if not alive:
        raise ValueError("В бою не осталось целей")
    target = alive[0]
    natural = roller.randint(1, 20)
    total = natural + spell_modifier
    critical = natural == 20
    success = critical or (natural != 1 and total >= target["ac"])
    damage = 0
    defeated = False
    if success:
        dice_count = 2 if critical else 1
        damage = sum(roller.randint(1, spell["damage_die"]) for _ in range(dice_count)) + max(0, spell_modifier)
        damage = max(1, damage)
        target["hp"] = max(0, target["hp"] - damage)
        if target["hp"] == 0:
            target["alive"] = False
            defeated = True
    state["round"] = state.get("round", 1) + 1
    return {
        "target": target,
        "natural": natural,
        "total": total,
        "success": success,
        "critical": critical,
        "damage": damage,
        "defeated": defeated,
        "xp": target["xp"] if defeated else 0,
    }
