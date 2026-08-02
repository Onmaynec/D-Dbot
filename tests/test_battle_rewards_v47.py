from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from app.battle_rewards import (
    calculate_battle_reward,
    grant_battle_reward,
    list_recent_rewards,
)
from app.party_combat import PartyCombatStore, prepare_party_state


def _character(name: str, xp: int = 0) -> dict:
    return {
        "name": name,
        "level": 3,
        "xp": xp,
        "max_hp": 30,
        "current_hp": 30,
        "abilities": {
            "СИЛ": 16,
            "ЛОВ": 14,
            "ТЕЛ": 12,
            "ИНТ": 10,
            "МДР": 15,
            "ХАР": 8,
        },
    }


def _member(user_id: int, name: str, xp: int = 0) -> dict:
    return {
        "user_id": user_id,
        "display_name": f"Player {user_id}",
        "character": _character(name, xp=xp),
    }


def _state(enemy_hp: int = 1) -> dict:
    return {
        "round": 2,
        "party_level": 3,
        "enemies": [
            {
                "id": 1,
                "name": "орк",
                "min_level": 2,
                "hp": enemy_hp,
                "max_hp": 20,
                "ac": 10,
                "xp": 55,
                "alive": enemy_hp > 0,
                "attack_bonus": 3,
                "damage_die": 6,
            },
            {
                "id": 2,
                "name": "культист",
                "min_level": 2,
                "hp": 0,
                "max_hp": 15,
                "ac": 12,
                "xp": 45,
                "alive": False,
                "attack_bonus": 3,
                "damage_die": 6,
            },
        ],
    }


def _schema(path: Path, members: list[dict]) -> None:
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


def test_reward_calculation_is_deterministic() -> None:
    state = prepare_party_state(_state(), [_member(1, "А"), _member(2, "Б")])
    first = calculate_battle_reward(state)
    second = calculate_battle_reward(state)

    assert first == second
    assert first.party_size == 2
    assert first.total_enemy_xp == 100
    assert first.xp_each == 50
    assert first.gold > 0
    assert first.quantity == 1


def test_grant_is_idempotent_and_updates_shared_economy(tmp_path: Path) -> None:
    path = tmp_path / "reward.sqlite3"
    members = [_member(1, "А", xp=10), _member(2, "Б", xp=20)]
    _schema(path, members)
    state = prepare_party_state(_state(), members)

    with sqlite3.connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        reward = grant_battle_reward(connection, 1, state)
        connection.commit()

    with sqlite3.connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        duplicate = grant_battle_reward(connection, 1, state)
        connection.commit()
        gold = connection.execute(
            "SELECT gold FROM party_wallets WHERE chat_id = 1"
        ).fetchone()[0]
        inventory = connection.execute(
            "SELECT item_name, quantity FROM inventory WHERE chat_id = 1"
        ).fetchone()
        history = connection.execute(
            "SELECT COUNT(*) FROM battle_reward_history WHERE chat_id = 1"
        ).fetchone()[0]

    assert duplicate == reward
    assert gold == 100 + reward.gold
    assert inventory == (reward.item_name, 1)
    assert history == 1
    assert state["party"][0]["character"]["xp"] == 10 + reward.xp_each
    assert state["party"][1]["character"]["xp"] == 20 + reward.xp_each


def _winning_attack(state, target_text, attack_modifier, damage_modifier):
    target = state["enemies"][0]
    target["hp"] = 0
    target["alive"] = False
    return {
        "target": target,
        "natural": 20,
        "total": 25,
        "hit": True,
        "critical": True,
        "damage": 99,
        "defeated": True,
        "xp": target["xp"],
    }


def _winning_spell(state, spell, spell_modifier):
    target = state["enemies"][0]
    target["hp"] = 0
    target["alive"] = False
    return {
        "target": target,
        "natural": 18,
        "total": 23,
        "success": True,
        "critical": False,
        "damage": 99,
        "defeated": True,
        "xp": target["xp"],
    }


def test_victory_grants_reward_in_same_transaction(tmp_path: Path) -> None:
    path = tmp_path / "victory.sqlite3"
    members = [_member(1, "А"), _member(2, "Б")]
    _schema(path, members)
    store = PartyCombatStore(path)
    asyncio.run(store.start(1, _state(), members))

    with patch("app.party_combat.attack", side_effect=_winning_attack):
        result = asyncio.run(store.attack(1, 1, "1"))

    assert result.allowed
    assert result.victory
    assert result.reward is not None

    with sqlite3.connect(path) as connection:
        combat = connection.execute(
            "SELECT state_json FROM combats WHERE chat_id = 1"
        ).fetchone()
        gold = connection.execute(
            "SELECT gold FROM party_wallets WHERE chat_id = 1"
        ).fetchone()[0]
        history = connection.execute(
            "SELECT COUNT(*) FROM battle_reward_history WHERE chat_id = 1"
        ).fetchone()[0]
        stored = connection.execute(
            """
            SELECT user_id, character_json
            FROM party_members
            WHERE chat_id = 1
            ORDER BY user_id
            """
        ).fetchall()

    assert combat is None
    assert history == 1
    assert gold == 100 + result.reward.gold
    xp_values = [json.loads(row[1])["xp"] for row in stored]
    assert xp_values[0] == 55 + result.reward.xp_each
    assert xp_values[1] == result.reward.xp_each


def test_repeated_final_click_cannot_duplicate_reward(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.sqlite3"
    members = [_member(1, "А")]
    _schema(path, members)
    store = PartyCombatStore(path)
    asyncio.run(store.start(1, _state(), members))

    with patch("app.party_combat.attack", side_effect=_winning_attack):
        first = asyncio.run(store.attack(1, 1, "1"))
        second = asyncio.run(store.attack(1, 1, "1"))

    assert first.victory
    assert not second.allowed
    with sqlite3.connect(path) as connection:
        history = connection.execute(
            "SELECT COUNT(*) FROM battle_reward_history WHERE chat_id = 1"
        ).fetchone()[0]
        quantity = connection.execute(
            "SELECT quantity FROM inventory WHERE chat_id = 1"
        ).fetchone()[0]
    assert history == 1
    assert quantity == 1


def test_spell_victory_and_recent_history(tmp_path: Path) -> None:
    path = tmp_path / "spell.sqlite3"
    members = [_member(1, "Маг")]
    _schema(path, members)
    store = PartyCombatStore(path)
    asyncio.run(store.start(1, _state(), members))

    with patch("app.party_combat.cast_spell", side_effect=_winning_spell):
        result = asyncio.run(
            store.spell(
                1,
                1,
                {"name": "Ледяное копьё", "damage_die": 8},
            )
        )

    assert result.victory
    assert result.reward is not None
    recent = list_recent_rewards(path, 1)
    assert len(recent) == 1
    assert recent[0]["xp_each"] == result.reward.xp_each
    assert recent[0]["item_name"] == result.reward.item_name
