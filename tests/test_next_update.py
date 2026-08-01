import random

from app.combat import enemy_phase, roll_initiative, start_combat
from app.gameplay import calculate_party_level, get_shop_item, use_healing_item


def test_party_level_uses_average() -> None:
    members = [{"character": {"level": 2}}, {"character": {"level": 4}}]
    assert calculate_party_level(members) == 3


def test_shop_item_lookup() -> None:
    assert get_shop_item(0)["price"] == 25


def test_healing_item_does_not_overheal() -> None:
    character = {"current_hp": 8, "max_hp": 10}
    result = use_healing_item(character, "Зелье лечения", random.Random(1))
    assert character["current_hp"] == 10
    assert result["restored"] == 2


def test_initiative_is_saved() -> None:
    state = start_combat(2, random.Random(2))
    order = roll_initiative(state, 3, random.Random(3))
    assert state["initiative_order"] == order
    assert len(order) == len(state["enemies"]) + 1


def test_enemy_phase_advances_round_and_damages() -> None:
    state = start_combat(3, random.Random(4))
    before = state["round"]
    result = enemy_phase(state, 30, 1, random.Random(5))
    assert state["round"] == before + 1
    assert result["current_hp"] < 30
