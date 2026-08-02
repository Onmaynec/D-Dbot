from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import app.casino as casino_module
import app.combat as combat_module
import app.story_choices as choices_module
from app.casino import CasinoStore
from app.combat_choices import CombatChoiceStore
from app.equipment import EquipmentStore, equipment_bonuses
from app.party_combat import prepare_party_state, resolve_party_enemy_phase
from app.story_choices import StoryChoiceStore


def _character(name: str = "Герой", hp: int = 30) -> dict:
    return {
        "name": name,
        "race": "человек",
        "class": "воин",
        "background": "странник",
        "level": 2,
        "xp": 0,
        "max_hp": hp,
        "current_hp": hp,
        "abilities": {
            "СИЛ": 16,
            "ЛОВ": 14,
            "ТЕЛ": 12,
            "ИНТ": 14,
            "МДР": 14,
            "ХАР": 14,
        },
    }


def _base_schema(path: Path, members: list[tuple[int, dict]], gold: int = 500) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE party_members (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                display_name TEXT NOT NULL,
                character_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(chat_id, user_id)
            );

            CREATE TABLE combats (
                chat_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE party_wallets (
                chat_id INTEGER PRIMARY KEY,
                gold INTEGER NOT NULL DEFAULT 100 CHECK(gold >= 0)
            );

            CREATE TABLE inventory (
                chat_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                rarity TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity >= 0),
                PRIMARY KEY(chat_id, item_name)
            );
            """
        )
        connection.execute("INSERT INTO party_wallets(chat_id, gold) VALUES (1, ?)", (gold,))
        for user_id, character in members:
            connection.execute(
                """
                INSERT INTO party_members(
                    chat_id, user_id, display_name, character_json, created_at
                ) VALUES (1, ?, ?, ?, 'now')
                """,
                (
                    user_id,
                    f"Player {user_id}",
                    json.dumps(character, ensure_ascii=False),
                ),
            )
        connection.commit()


def test_equipment_purchase_equip_and_bonuses(tmp_path: Path) -> None:
    path = tmp_path / "equipment.sqlite3"
    _base_schema(path, [(7, _character())])
    store = EquipmentStore(path)

    bought = asyncio.run(store.buy(1, 7, "war_axe"))
    equipped = asyncio.run(store.equip(1, 7, "war_axe"))
    snapshot = asyncio.run(store.snapshot(1, 7))

    assert bought.ok
    assert bought.balance == 325
    assert equipped.ok
    assert snapshot["equipped"]["weapon"] == "Секира налётчика"
    assert snapshot["bonuses"]["damage"] == 3
    assert snapshot["character"]["equipment"]["weapon"] == "war_axe"

    with sqlite3.connect(path) as connection:
        history = connection.execute(
            "SELECT action FROM equipment_history ORDER BY id"
        ).fetchall()
    assert history == [("buy",), ("equip",)]


def test_equipment_cannot_change_during_combat(tmp_path: Path) -> None:
    path = tmp_path / "equipment-lock.sqlite3"
    _base_schema(path, [(7, _character())])
    store = EquipmentStore(path)
    assert asyncio.run(store.buy(1, 7, "leather_armor")).ok
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO combats(chat_id, state_json, updated_at) VALUES (1, '{}', 'now')"
        )
        connection.commit()

    result = asyncio.run(store.equip(1, 7, "leather_armor"))

    assert not result.ok
    assert "во время активного боя" in result.reason


def test_casino_updates_shared_wallet_atomically(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "casino.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE party_wallets(chat_id INTEGER PRIMARY KEY, gold INTEGER NOT NULL)"
        )
        connection.execute("INSERT INTO party_wallets VALUES (1, 100)")
        connection.commit()
    monkeypatch.setattr(
        casino_module,
        "_coin",
        lambda: (2, "Монета благоволит партии", "Орёл"),
    )

    result = asyncio.run(CasinoStore(path).play(1, 8, "coin", 25))

    assert result.ok
    assert result.net == 25
    assert result.balance == 125
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT bet, payout, net FROM casino_history"
        ).fetchone()
    assert row == (25, 50, 25)


def test_casino_rejects_bet_without_money(tmp_path: Path) -> None:
    path = tmp_path / "casino-poor.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE party_wallets(chat_id INTEGER PRIMARY KEY, gold INTEGER NOT NULL)"
        )
        connection.execute("INSERT INTO party_wallets VALUES (1, 5)")
        connection.commit()

    result = asyncio.run(CasinoStore(path).play(1, 8, "dice", 10))

    assert not result.ok
    with sqlite3.connect(path) as connection:
        balance = connection.execute(
            "SELECT gold FROM party_wallets WHERE chat_id = 1"
        ).fetchone()[0]
        count = connection.execute("SELECT COUNT(*) FROM casino_history").fetchone()[0]
    assert balance == 5
    assert count == 0


def test_story_choice_success_grants_gold_and_item(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "choice.sqlite3"
    _base_schema(path, [(1, _character()), (2, _character())], gold=100)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE active_story_choices(chat_id INTEGER PRIMARY KEY, scenario_code TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO active_story_choices VALUES (1, 'broken_bridge', 'now')"
        )
        connection.commit()
    monkeypatch.setattr(choices_module.secrets, "randbelow", lambda _: 19)

    result = asyncio.run(StoryChoiceStore(path).resolve(1, 1, "leap"))

    assert result.ok
    assert result.success
    assert result.natural == 20
    assert result.gold_delta == 45
    assert result.item_name == "Серебряные стрелы"
    with sqlite3.connect(path) as connection:
        balance = connection.execute(
            "SELECT gold FROM party_wallets WHERE chat_id = 1"
        ).fetchone()[0]
        item = connection.execute(
            "SELECT quantity FROM inventory WHERE chat_id = 1 AND item_name = 'Серебряные стрелы'"
        ).fetchone()[0]
    assert balance == 145
    assert item == 1


def test_story_choice_failure_damages_party(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "choice-fail.sqlite3"
    _base_schema(path, [(1, _character(hp=20)), (2, _character(hp=20))], gold=100)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE active_story_choices(chat_id INTEGER PRIMARY KEY, scenario_code TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO active_story_choices VALUES (1, 'cursed_shrine', 'now')"
        )
        connection.commit()
    monkeypatch.setattr(choices_module.secrets, "randbelow", lambda _: 0)

    result = asyncio.run(StoryChoiceStore(path).resolve(1, 1, "break"))

    assert result.ok
    assert not result.success
    assert result.damage_each == 6
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT character_json FROM party_members ORDER BY user_id"
        ).fetchall()
    assert [json.loads(row[0])["current_hp"] for row in rows] == [14, 14]


class _FixedEnemyRng:
    def choice(self, items: list[dict]) -> dict:
        return items[0]

    def randint(self, _minimum: int, _maximum: int) -> int:
        return 10


def test_guard_and_equipment_raise_armor_class() -> None:
    character = _character(hp=30)
    character["equipment"] = {
        "armor": "chainmail",
        "trinket": "guardian_signet",
    }
    members = [
        {
            "user_id": 1,
            "display_name": "Tank",
            "character": character,
        }
    ]
    state = prepare_party_state(
        {
            "round": 1,
            "party_level": 2,
            "enemies": [
                {
                    "id": 1,
                    "name": "орк",
                    "min_level": 2,
                    "hp": 20,
                    "max_hp": 20,
                    "ac": 12,
                    "xp": 50,
                    "alive": True,
                    "attack_bonus": 3,
                    "damage_die": 6,
                }
            ],
        },
        members,
    )
    state["guard_user_ids"] = [1]
    state["acted_user_ids"] = [1]

    phase = resolve_party_enemy_phase(state, _FixedEnemyRng())

    event = phase["events"][0]
    assert event["guarded"]
    assert event["equipment_armor"] == 3
    assert event["guard_armor"] == 5
    assert event["armor_class"] == 20
    assert not event["hit"]
    assert state["guard_user_ids"] == []


def test_power_attack_uses_weapon_and_grants_victory_reward(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "power.sqlite3"
    character = _character(hp=30)
    character["equipment"] = {"weapon": "war_axe"}
    _base_schema(path, [(1, character)], gold=100)
    member = {
        "user_id": 1,
        "display_name": "Player 1",
        "character": character,
    }
    state = prepare_party_state(
        {
            "round": 1,
            "party_level": 2,
            "enemies": [
                {
                    "id": 1,
                    "name": "гоблин",
                    "min_level": 1,
                    "hp": 1,
                    "max_hp": 1,
                    "ac": 1,
                    "xp": 25,
                    "alive": True,
                    "attack_bonus": 2,
                    "damage_die": 6,
                }
            ],
        },
        [member],
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO combats(chat_id, state_json, updated_at) VALUES (1, ?, 'now')",
            (json.dumps(state, ensure_ascii=False),),
        )
        connection.commit()
    rolls = iter([10, 4])
    monkeypatch.setattr(combat_module.random, "randint", lambda _a, _b: next(rolls))

    result = asyncio.run(CombatChoiceStore(path).power_attack(1, 1, "1"))

    assert result.ok
    assert result.victory
    assert result.action is not None
    assert result.action["equipment_damage_bonus"] == 3
    assert result.reward is not None
    with sqlite3.connect(path) as connection:
        combat_count = connection.execute("SELECT COUNT(*) FROM combats").fetchone()[0]
        reward_count = connection.execute(
            "SELECT COUNT(*) FROM battle_reward_history"
        ).fetchone()[0]
        history_count = connection.execute(
            "SELECT COUNT(*) FROM combat_choice_history"
        ).fetchone()[0]
    assert combat_count == 0
    assert reward_count == 1
    assert history_count == 1


def test_equipment_bonus_helper_ignores_unknown_codes() -> None:
    bonuses = equipment_bonuses(
        {
            "equipment": {
                "weapon": "void_blade",
                "armor": "missing-item",
                "trinket": "lucky_charm",
            }
        }
    )
    assert bonuses == {
        "damage": 6,
        "armor": 0,
        "spell_damage": 1,
        "guard": 0,
    }
