from __future__ import annotations

import random
from typing import Any, Iterable

LOCATION_PREFIXES = (
    "Забытый", "Пепельный", "Лунный", "Стеклянный", "Багровый", "Безмолвный",
    "Звёздный", "Грозовой", "Туманный", "Медный",
)
LOCATION_PLACES = (
    "перевал", "город", "порт", "лес", "каньон", "монастырь", "архипелаг",
    "некрополь", "форпост", "рынок", "кратер", "лабиринт",
)
BIOMES = (
    "горные пики", "древний лес", "пустошь", "ледяная равнина", "подземные руины",
    "космическая колония", "затопленные храмы", "готические кварталы",
)
DANGERS = (
    "дорога кажется безопасной, но слишком тихой",
    "местность контролируют наёмники",
    "в тумане слышны шаги невидимого существа",
    "магические бури искажают пространство",
    "по ночам здесь исчезают путники",
    "местные требуют плату за каждый костёр",
)
DISCOVERIES = (
    "разрушенный путевой алтарь",
    "тайный склад контрабандистов",
    "каменная дверь без замочной скважины",
    "следы каравана, пропавшего много лет назад",
    "обломок карты, указывающий на скрытый путь",
    "маленькое святилище неизвестной фракции",
)

ACHIEVEMENTS: tuple[dict[str, str], ...] = (
    {"code": "first_contract", "title": "Первый контракт", "description": "Завершить первый активный квест."},
    {"code": "pathfinder", "title": "Следопыт", "description": "Посетить три разные точки путешествия."},
    {"code": "trusted_ally", "title": "Надёжный союзник", "description": "Достичь репутации +3 с любой фракцией."},
    {"code": "quest_veteran", "title": "Ветеран контрактов", "description": "Завершить пять активных квестов."},
    {"code": "living_legend", "title": "Живая легенда", "description": "Завершить десять квестов и посетить десять локаций."},
)


def build_tracked_quest(
    quest: dict[str, str], factions: Iterable[str], rng: random.Random | None = None
) -> dict[str, Any]:
    roller = rng or random
    faction_pool = [name for name in factions if name]
    target = roller.randint(2, 4)
    gold_reward = target * 30 + roller.randint(10, 35)
    faction = roller.choice(faction_pool) if faction_pool else "Лига вольных искателей"
    return {
        "title": f"Контракт: {quest['goal'].capitalize()}",
        "giver": quest["giver"],
        "goal": quest["goal"],
        "reward_text": quest["reward"],
        "complication": quest["complication"],
        "faction_name": faction,
        "progress": 0,
        "target": target,
        "gold_reward": gold_reward,
        "reputation_reward": 2 if target == 4 else 1,
        "status": "active",
    }


def advance_progress(current: int, target: int, amount: int = 1) -> int:
    if target <= 0:
        raise ValueError("Цель прогресса должна быть положительной")
    return min(target, max(0, current) + max(0, amount))


def reputation_rank(score: int) -> str:
    if score <= -6:
        return "заклятые враги"
    if score <= -3:
        return "враждебность"
    if score <= -1:
        return "недоверие"
    if score == 0:
        return "нейтрально"
    if score <= 2:
        return "уважение"
    if score <= 5:
        return "союзники"
    return "легендарные друзья"


def generate_location(
    campaign: dict[str, Any] | None, rng: random.Random | None = None
) -> dict[str, Any]:
    roller = rng or random
    factions = list((campaign or {}).get("factions", []))
    faction = roller.choice(factions) if factions else "Лига вольных искателей"
    return {
        "name": f"{roller.choice(LOCATION_PREFIXES)} {roller.choice(LOCATION_PLACES)}",
        "biome": roller.choice(BIOMES),
        "danger": roller.choice(DANGERS),
        "discovery": roller.choice(DISCOVERIES),
        "faction_name": faction,
        "gold_found": roller.randint(5, 25),
        "reputation_delta": 1 if roller.random() < 0.35 else 0,
    }


def achievement_candidates(
    stats: dict[str, int], reputation: dict[str, int]
) -> list[dict[str, str]]:
    completed = int(stats.get("quests_completed", 0))
    visited = int(stats.get("locations_visited", 0))
    best_reputation = max(reputation.values(), default=0)
    unlocked_codes: set[str] = set()
    if completed >= 1:
        unlocked_codes.add("first_contract")
    if visited >= 3:
        unlocked_codes.add("pathfinder")
    if best_reputation >= 3:
        unlocked_codes.add("trusted_ally")
    if completed >= 5:
        unlocked_codes.add("quest_veteran")
    if completed >= 10 and visited >= 10:
        unlocked_codes.add("living_legend")
    return [item for item in ACHIEVEMENTS if item["code"] in unlocked_codes]
