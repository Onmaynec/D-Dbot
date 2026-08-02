import asyncio
import sqlite3
from pathlib import Path

from app.forge import ForgeStore, item_code, salvage_value


def seed(path: Path, *, gold: int = 100, items: dict[str, tuple[str, int]] | None = None) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE inventory (
                chat_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                rarity TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                PRIMARY KEY(chat_id, item_name)
            );
            CREATE TABLE party_wallets (
                chat_id INTEGER PRIMARY KEY,
                gold INTEGER NOT NULL
            );
            """
        )
        connection.execute("INSERT INTO party_wallets(chat_id, gold) VALUES (1, ?)", (gold,))
        for name, (rarity, quantity) in (items or {}).items():
            connection.execute(
                "INSERT INTO inventory(chat_id, item_name, rarity, quantity) VALUES (1, ?, ?, ?)",
                (name, rarity, quantity),
            )
        connection.commit()


def inventory(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT item_name, quantity FROM inventory WHERE chat_id = 1 ORDER BY item_name"
        ).fetchall()
    return {str(name): int(quantity) for name, quantity in rows}


def gold(path: Path) -> int:
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT gold FROM party_wallets WHERE chat_id = 1").fetchone()
    return int(row[0])


def test_craft_consumes_resources_atomically(tmp_path: Path) -> None:
    path = tmp_path / "forge.sqlite3"
    seed(path, gold=50, items={"Зелье лечения": ("обычная", 3)})
    forge = ForgeStore(path)

    result = asyncio.run(forge.craft(1, 10, "greater_healing"))

    assert result.crafted is True
    assert result.gold_balance == 35
    assert inventory(path) == {"Большое зелье лечения": 1, "Зелье лечения": 1}


def test_failed_craft_does_not_change_inventory_or_gold(tmp_path: Path) -> None:
    path = tmp_path / "forge.sqlite3"
    seed(path, gold=10, items={"Зелье лечения": ("обычная", 1)})
    forge = ForgeStore(path)
    before_items = inventory(path)

    result = asyncio.run(forge.craft(1, 10, "greater_healing"))

    assert result.crafted is False
    assert result.missing == {"Зелье лечения": 1}
    assert inventory(path) == before_items
    assert gold(path) == 10


def test_salvage_decrements_stack_and_adds_gold(tmp_path: Path) -> None:
    path = tmp_path / "forge.sqlite3"
    seed(path, gold=25, items={"Свиток щита": ("редкая", 2)})
    forge = ForgeStore(path)

    result = asyncio.run(forge.salvage(1, 10, item_code("Свиток щита")))

    assert result.salvaged is True
    assert result.gold_received == 15
    assert result.gold_balance == 40
    assert inventory(path) == {"Свиток щита": 1}


def test_unknown_salvage_code_keeps_state(tmp_path: Path) -> None:
    path = tmp_path / "forge.sqlite3"
    seed(path, gold=25, items={"Перо феникса": ("эпическая", 1)})
    forge = ForgeStore(path)

    result = asyncio.run(forge.salvage(1, 10, "not-found"))

    assert result.salvaged is False
    assert inventory(path) == {"Перо феникса": 1}
    assert gold(path) == 25


def test_codes_and_values_are_stable() -> None:
    assert item_code("Зелье лечения") == item_code("Зелье лечения")
    assert len(item_code("Зелье лечения")) == 10
    assert salvage_value("легендарная") == 120
    assert salvage_value("неизвестная") == 5
