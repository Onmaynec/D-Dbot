from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from app.party_support import PartySupportStore


def _character(name: str, hp: int, maximum: int = 20) -> dict:
    return {
        "name": name,
        "race": "Человек",
        "class": "Воин",
        "level": 2,
        "xp": 0,
        "current_hp": hp,
        "max_hp": maximum,
        "abilities": {
            "СИЛ": 14,
            "ЛОВ": 12,
            "ТЕЛ": 12,
            "ИНТ": 10,
            "МДР": 12,
            "ХАР": 10,
        },
    }


def _member(user_id: int, name: str, hp: int, maximum: int = 20) -> dict:
    return {
        "user_id": user_id,
        "display_name": f"Игрок {user_id}",
        "character": _character(name, hp, maximum),
    }


def _state(
    first_hp: int = 20,
    second_hp: int = 5,
    first_max: int = 20,
    second_max: int = 20,
    acted: list[int] | None = None,
) -> dict:
    return {
        "round": 1,
        "party_mode": True,
        "acted_user_ids": acted or [],
        "party": [
            _member(1, "Альрик", first_hp, first_max),
            _member(2, "Мира", second_hp, second_max),
        ],
        "enemies": [
            {
                "id": 1,
                "name": "Гоблин",
                "hp": 12,
                "max_hp": 12,
                "ac": 10,
                "attack_bonus": -100,
                "damage_die": 4,
                "xp": 20,
                "alive": True,
            }
        ],
    }


def _prepare_database(
    path: Path,
    state: dict,
    inventory: dict[str, tuple[str, int]],
) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE combats (
                chat_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE party_members (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                display_name TEXT NOT NULL,
                character_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(chat_id, user_id)
            );

            CREATE TABLE inventory (
                chat_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                rarity TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                PRIMARY KEY(chat_id, item_name)
            );
            """
        )
        connection.execute(
            """
            INSERT INTO combats(chat_id, state_json, updated_at)
            VALUES (10, ?, 'сейчас')
            """,
            (json.dumps(state, ensure_ascii=False),),
        )
        for member in state["party"]:
            connection.execute(
                """
                INSERT INTO party_members(
                    chat_id,
                    user_id,
                    display_name,
                    character_json,
                    created_at
                )
                VALUES (10, ?, ?, ?, 'сейчас')
                """,
                (
                    member["user_id"],
                    member["display_name"],
                    json.dumps(member["character"], ensure_ascii=False),
                ),
            )
        for item_name, (rarity, quantity) in inventory.items():
            connection.execute(
                """
                INSERT INTO inventory(chat_id, item_name, rarity, quantity)
                VALUES (10, ?, ?, ?)
                """,
                (item_name, rarity, quantity),
            )
        connection.commit()


def _read_quantity(path: Path, item_name: str) -> int:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            """
            SELECT quantity
            FROM inventory
            WHERE chat_id = 10 AND item_name = ?
            """,
            (item_name,),
        ).fetchone()
    return int(row[0]) if row else 0


def _read_state(path: Path) -> dict:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT state_json FROM combats WHERE chat_id = 10"
        ).fetchone()
    return json.loads(row[0])


def _read_member_hp(path: Path, user_id: int) -> int:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            """
            SELECT character_json
            FROM party_members
            WHERE chat_id = 10 AND user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return int(json.loads(row[0])["current_hp"])


def test_heal_consumes_item_marks_turn_and_persists(tmp_path: Path) -> None:
    path = tmp_path / "support.sqlite3"
    _prepare_database(
        path,
        _state(),
        {"Зелье лечения": ("обычная", 2)},
    )
    store = PartySupportStore(path)

    result = asyncio.run(store.heal(10, 1, 2, "small"))

    assert result.allowed is True
    assert result.restored > 0
    assert result.remaining == 1
    assert 1 in result.state["acted_user_ids"]
    assert _read_quantity(path, "Зелье лечения") == 1
    assert _read_member_hp(path, 2) == result.target["character"]["current_hp"]


def test_healing_potion_revives_unconscious_member(tmp_path: Path) -> None:
    path = tmp_path / "revive.sqlite3"
    _prepare_database(
        path,
        _state(second_hp=0),
        {"Зелье лечения": ("обычная", 1)},
    )
    store = PartySupportStore(path)

    result = asyncio.run(store.heal(10, 1, 2, "small"))

    assert result.allowed is True
    assert result.target["character"]["current_hp"] > 0
    assert _read_member_hp(path, 2) > 0
    assert _read_quantity(path, "Зелье лечения") == 0


def test_duplicate_support_turn_does_not_consume_second_item(
    tmp_path: Path,
) -> None:
    path = tmp_path / "duplicate.sqlite3"
    _prepare_database(
        path,
        _state(second_hp=1, second_max=100),
        {"Зелье лечения": ("обычная", 3)},
    )
    store = PartySupportStore(path)

    first = asyncio.run(store.heal(10, 1, 2, "small"))
    second = asyncio.run(store.heal(10, 1, 2, "small"))

    assert first.allowed is True
    assert second.allowed is False
    assert "уже действовал" in second.reason
    assert _read_quantity(path, "Зелье лечения") == 2


def test_missing_item_rolls_back_turn_and_health(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"
    _prepare_database(path, _state(second_hp=3), {})
    store = PartySupportStore(path)

    result = asyncio.run(store.heal(10, 1, 2, "small"))

    assert result.allowed is False
    assert "нет предмета" in result.reason
    assert _read_member_hp(path, 2) == 3
    assert _read_state(path)["acted_user_ids"] == []


def test_last_support_action_triggers_enemy_phase(tmp_path: Path) -> None:
    path = tmp_path / "round.sqlite3"
    _prepare_database(
        path,
        _state(
            first_hp=100,
            second_hp=99,
            first_max=100,
            second_max=100,
            acted=[2],
        ),
        {"Большое зелье лечения": ("редкая", 1)},
    )
    store = PartySupportStore(path)

    result = asyncio.run(store.heal(10, 1, 2, "greater"))

    assert result.allowed is True
    assert result.round_complete is True
    assert result.defeat is False
    assert result.state["round"] == 2
    assert result.state["acted_user_ids"] == []
    assert len(result.enemy_events) == 1
    assert _read_state(path)["round"] == 2
