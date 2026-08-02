from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from app.party_combat import (
    PartyCombatStore,
    action_guard,
    pending_members,
    prepare_party_state,
    resolve_party_enemy_phase,
    round_ready,
)


def _character(name: str, hp: int = 30) -> dict:
    return {
        "name": name,
        "level": 2,
        "xp": 0,
        "max_hp": hp,
        "current_hp": hp,
        "abilities": {
            "СИЛ": 16,
            "ЛОВ": 14,
            "ТЕЛ": 12,
            "ИНТ": 10,
            "МДР": 15,
            "ХАР": 8,
        },
    }


def _member(user_id: int, name: str, hp: int = 30) -> dict:
    return {
        "user_id": user_id,
        "display_name": f"Player {user_id}",
        "character": _character(name, hp),
    }


def _combat_state(enemy_hp: int = 999) -> dict:
    return {
        "round": 1,
        "party_level": 2,
        "enemies": [
            {
                "id": 1,
                "name": "орк",
                "min_level": 2,
                "hp": enemy_hp,
                "max_hp": enemy_hp,
                "ac": 10,
                "xp": 50,
                "alive": True,
                "attack_bonus": 3,
                "damage_die": 6,
            }
        ],
    }


def _base_schema(path: Path, members: list[dict]) -> None:
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
            """
        )
        for member in members:
            connection.execute(
                """
                INSERT INTO party_members(
                    chat_id, user_id, display_name, character_json, created_at
                )
                VALUES (1, ?, ?, ?, 'now')
                """,
                (
                    member["user_id"],
                    member["display_name"],
                    json.dumps(member["character"], ensure_ascii=False),
                ),
            )
        connection.commit()


def test_party_turn_guards_and_pending_members() -> None:
    state = prepare_party_state(
        _combat_state(),
        [_member(1, "А"), _member(2, "Б")],
    )

    assert action_guard(state, 99).startswith("Сначала вступи")
    assert action_guard(state, 1) == ""

    state["acted_user_ids"] = [1]
    assert action_guard(state, 1) == "Ты уже действовал в этом раунде."
    assert [member["user_id"] for member in pending_members(state)] == [2]
    assert not round_ready(state)

    state["acted_user_ids"] = [1, 2]
    assert round_ready(state)


class _FixedRng:
    def __init__(self) -> None:
        self.values = iter([20, 6, 6])

    def choice(self, items: list[dict]) -> dict:
        return items[0]

    def randint(self, _minimum: int, _maximum: int) -> int:
        return next(self.values)


def test_enemy_phase_targets_living_member_and_triggers_phoenix() -> None:
    members = [_member(1, "А", hp=20), _member(2, "Б", hp=20)]
    members[0]["character"]["current_hp"] = 5
    state = prepare_party_state(_combat_state(), members)
    state["shield_rounds"] = 2
    state["phoenix_ready"] = True
    state["acted_user_ids"] = [1, 2]

    result = resolve_party_enemy_phase(state, _FixedRng())

    event = result["events"][0]
    assert event["target_user_id"] == 1
    assert event["critical"]
    assert event["revived"]
    assert state["party"][0]["character"]["current_hp"] == 10
    assert state["round"] == 2
    assert state["acted_user_ids"] == []
    assert state["shield_rounds"] == 1
    assert not result["defeat"]


def test_store_rejects_duplicate_turn_before_party_finishes(tmp_path: Path) -> None:
    members = [_member(1, "А", hp=1000), _member(2, "Б", hp=1000)]
    path = tmp_path / "party.sqlite3"
    _base_schema(path, members)
    store = PartyCombatStore(path)
    asyncio.run(store.start(1, _combat_state(), members))

    first = asyncio.run(store.attack(1, 1, "1"))
    duplicate = asyncio.run(store.attack(1, 1, "1"))

    assert first.allowed
    assert not first.round_complete
    assert not duplicate.allowed
    assert duplicate.reason == "Ты уже действовал в этом раунде."

    with sqlite3.connect(path) as connection:
        state = json.loads(
            connection.execute(
                "SELECT state_json FROM combats WHERE chat_id = 1"
            ).fetchone()[0]
        )
    assert state["acted_user_ids"] == [1]


def test_store_runs_enemy_phase_after_last_living_member(tmp_path: Path) -> None:
    members = [_member(1, "А", hp=1000), _member(2, "Б", hp=1000)]
    path = tmp_path / "round.sqlite3"
    _base_schema(path, members)
    store = PartyCombatStore(path)
    asyncio.run(store.start(1, _combat_state(), members))

    asyncio.run(store.attack(1, 1, "1"))
    result = asyncio.run(store.attack(1, 2, "1"))

    assert result.allowed
    assert result.round_complete
    assert result.state is not None
    assert result.state["round"] == 2
    assert result.state["acted_user_ids"] == []
    assert len(result.enemy_events) == 1

    with sqlite3.connect(path) as connection:
        stored_state = json.loads(
            connection.execute(
                "SELECT state_json FROM combats WHERE chat_id = 1"
            ).fetchone()[0]
        )
        history_count = connection.execute(
            "SELECT COUNT(*) FROM party_combat_history WHERE chat_id = 1"
        ).fetchone()[0]
        stored_members = connection.execute(
            """
            SELECT user_id, character_json
            FROM party_members
            WHERE chat_id = 1
            ORDER BY user_id
            """
        ).fetchall()

    assert stored_state["round"] == 2
    assert history_count == 2
    assert [
        json.loads(row[1])["current_hp"]
        for row in stored_members
    ] == [
        member["character"]["current_hp"]
        for member in result.state["party"]
    ]


def test_store_records_spell_turn(tmp_path: Path) -> None:
    members = [_member(1, "Маг", hp=1000), _member(2, "Воин", hp=1000)]
    path = tmp_path / "spell.sqlite3"
    _base_schema(path, members)
    store = PartyCombatStore(path)
    asyncio.run(store.start(1, _combat_state(), members))

    result = asyncio.run(
        store.spell(
            1,
            1,
            {
                "name": "Ледяное копьё",
                "damage_die": 8,
            },
        )
    )

    assert result.allowed
    assert not result.round_complete
    with sqlite3.connect(path) as connection:
        action_type = connection.execute(
            """
            SELECT action_type
            FROM party_combat_history
            WHERE chat_id = 1
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()[0]
    assert action_type == "spell"
