from __future__ import annotations

import random

import pytest

from app.combat import attack, living_enemies, start_combat
from app.dice import ability_modifier, parse_and_roll
from app.generators import generate_campaign, generate_character, generate_loot, generate_quest


def test_roll_supports_d20_with_modifier() -> None:
    result = parse_and_roll("2d20+3", random.Random(7))
    assert len(result.rolls) == 2
    assert result.total == sum(result.rolls) + 3


def test_roll_rejects_unknown_die() -> None:
    with pytest.raises(ValueError):
        parse_and_roll("d7")


def test_ability_modifier() -> None:
    assert ability_modifier(10) == 0
    assert ability_modifier(16) == 3
    assert ability_modifier(7) == -2


def test_character_has_complete_sheet() -> None:
    character = generate_character(random.Random(42))
    assert set(character["abilities"]) == {"СИЛ", "ЛОВ", "ТЕЛ", "ИНТ", "МДР", "ХАР"}
    assert character["current_hp"] == character["max_hp"]
    assert character["level"] == 1


def test_campaign_has_three_unique_factions() -> None:
    campaign = generate_campaign("Тестовая кампания", random.Random(1))
    assert campaign["name"] == "Тестовая кампания"
    assert len(campaign["factions"]) == 3
    assert len(set(campaign["factions"])) == 3


def test_generators_include_campaign_context() -> None:
    quest = generate_quest("Пепельная Корона", random.Random(2))
    loot = generate_loot("Пепельная Корона", random.Random(3))
    assert quest["campaign"] == "Пепельная Корона"
    assert loot["campaign"] == "Пепельная Корона"


def test_combat_attack_changes_enemy_hp() -> None:
    rng = random.Random(10)
    state = start_combat(3, rng)
    target = living_enemies(state)[0]
    before = target["hp"]
    result = attack(state, str(target["id"]), 100, 3, rng)
    assert result["hit"] is True
    assert target["hp"] < before
