import asyncio
import json
import sqlite3
from pathlib import Path

from app.tactical_items import (
    PHOENIX_FEATHER,
    SHIELD_SCROLL,
    TacticalItemStore,
    advance_shield,
    armor_bonus,
    trigger_phoenix,
)


def create_combat_database(path: Path) -> None:
    state = {
        "round": 1,
        "enemies": [{"id": 1, "name": "орк", "hp": 12, "alive": True}],
    }
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE combats (
                chat_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
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
            "INSERT INTO combats(chat_id, state_json, updated_at) VALUES (1, ?, 'now')",
            (json.dumps(state, ensure_ascii=False),),
        )
        connection.commit()


def add_item(path: Path, item_name: str, quantity: int = 1) -> None:
    rarity = "эпическая" if item_name == PHOENIX_FEATHER else "редкая"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO inventory(chat_id, item_name, rarity, quantity) VALUES (1, ?, ?, ?)",
            (item_name, rarity, quantity),
        )
        connection.commit()


def item_quantity(path: Path, item_name: str) -> int:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT quantity FROM inventory WHERE chat_id = 1 AND item_name = ?",
            (item_name,),
        ).fetchone()
    return int(row[0]) if row else 0


def combat_state(path: Path) -> dict:
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT state_json FROM combats WHERE chat_id = 1").fetchone()
    return json.loads(row[0])


def test_shield_activation_consumes_item_and_persists_effect(tmp_path: Path) -> None:
    database = tmp_path / "game.sqlite3"
    create_combat_database(database)
    add_item(database, SHIELD_SCROLL, quantity=2)

    result = asyncio.run(TacticalItemStore(database).activate(1, 99, "shield"))

    assert result.activated is True
    assert result.remaining == 1
    assert result.state["shield_rounds"] == 2
    assert combat_state(database)["shield_rounds"] == 2
    assert item_quantity(database, SHIELD_SCROLL) == 1


def test_duplicate_shield_does_not_consume_second_item(tmp_path: Path) -> None:
    database = tmp_path / "game.sqlite3"
    create_combat_database(database)
    add_item(database, SHIELD_SCROLL, quantity=2)
    store = TacticalItemStore(database)

    first = asyncio.run(store.activate(1, 99, "shield"))
    second = asyncio.run(store.activate(1, 99, "shield"))

    assert first.activated is True
    assert second.activated is False
    assert "уже действует" in second.reason
    assert item_quantity(database, SHIELD_SCROLL) == 1


def test_phoenix_activation_and_trigger_revives_half_hp(tmp_path: Path) -> None:
    database = tmp_path / "game.sqlite3"
    create_combat_database(database)
    add_item(database, PHOENIX_FEATHER)

    result = asyncio.run(TacticalItemStore(database).activate(1, 99, "phoenix"))
    revived_hp = trigger_phoenix(result.state, 31)

    assert result.activated is True
    assert revived_hp == 15
    assert "phoenix_ready" not in result.state
    assert result.state["phoenix_uses"] == 1
    assert item_quantity(database, PHOENIX_FEATHER) == 0


def test_shield_bonus_expires_after_two_enemy_phases() -> None:
    state = {"shield_rounds": 2}

    assert armor_bonus(state) == 2
    assert advance_shield(state) is False
    assert state["shield_rounds"] == 1
    assert armor_bonus(state) == 2
    assert advance_shield(state) is True
    assert armor_bonus(state) == 0


def test_missing_item_does_not_change_combat(tmp_path: Path) -> None:
    database = tmp_path / "game.sqlite3"
    create_combat_database(database)
    before = combat_state(database)

    result = asyncio.run(TacticalItemStore(database).activate(1, 99, "shield"))

    assert result.activated is False
    assert "нет в инвентаре" in result.reason
    assert combat_state(database) == before
