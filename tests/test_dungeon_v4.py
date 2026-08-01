import random

from app.dungeon_logic import (
    boss_retaliation,
    create_dungeon,
    difficulty_label,
    explore_next_room,
    player_attack_boss,
    victory_rewards,
)


def test_difficulty_changes_dungeon_length() -> None:
    easy = create_dungeon(2, "easy", random.Random(1))
    hard = create_dungeon(2, "hard", random.Random(1))
    assert easy["max_depth"] == 4
    assert hard["max_depth"] == 6
    assert difficulty_label("hard") == "хардкор"


def test_final_room_always_contains_boss() -> None:
    state = create_dungeon(3, "normal", random.Random(2))
    room = None
    for index in range(state["max_depth"]):
        room = explore_next_room(state, random.Random(10 + index))
    assert room is not None
    assert room["type"] == "boss"
    assert state["boss"]["hp"] == state["boss"]["max_hp"]


def test_room_progress_is_persisted_in_state() -> None:
    state = create_dungeon(1, "normal", random.Random(3))
    room = explore_next_room(state, random.Random(4))
    assert state["depth"] == 1
    assert state["rooms"] == [room]


def test_player_can_defeat_boss_with_large_modifier() -> None:
    state = create_dungeon(1, "easy", random.Random(5))
    for index in range(state["max_depth"]):
        explore_next_room(state, random.Random(20 + index))
    state["boss"]["hp"] = 1
    result = player_attack_boss(state, 100, 100, random.Random(6))
    assert result["hit"] is True
    assert result["defeated"] is True


def test_boss_retaliation_and_rewards() -> None:
    state = create_dungeon(4, "hard", random.Random(7))
    for index in range(state["max_depth"]):
        explore_next_room(state, random.Random(30 + index))
    retaliation = boss_retaliation(state, 1, random.Random(8))
    rewards = victory_rewards(state)
    assert retaliation["hit"] is True
    assert retaliation["damage"] > 0
    assert rewards["gold"] > 0
    assert rewards["loot"]
