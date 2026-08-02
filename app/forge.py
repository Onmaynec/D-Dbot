from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SALVAGE_VALUES = {
    "обычная": 5,
    "редкая": 15,
    "эпическая": 45,
    "легендарная": 120,
}


@dataclass(frozen=True, slots=True)
class Recipe:
    code: str
    name: str
    rarity: str
    gold_cost: int
    ingredients: dict[str, int]
    description: str


@dataclass(frozen=True, slots=True)
class RecipeStatus:
    recipe: Recipe
    available: bool
    missing: dict[str, int]
    gold_balance: int


@dataclass(frozen=True, slots=True)
class ForgeSnapshot:
    gold_balance: int
    inventory: tuple[dict[str, Any], ...]
    recipes: tuple[RecipeStatus, ...]


@dataclass(frozen=True, slots=True)
class CraftResult:
    crafted: bool
    recipe: Recipe
    gold_balance: int
    missing: dict[str, int]


@dataclass(frozen=True, slots=True)
class SalvageResult:
    salvaged: bool
    item_name: str | None
    rarity: str | None
    gold_received: int
    gold_balance: int


RECIPES = (
    Recipe(
        code="greater_healing",
        name="Большое зелье лечения",
        rarity="редкая",
        gold_cost=15,
        ingredients={"Зелье лечения": 2},
        description="Объединить два обычных зелья в усиленное.",
    ),
    Recipe(
        code="shield_scroll",
        name="Свиток щита",
        rarity="редкая",
        gold_cost=20,
        ingredients={"Свиток удачи": 1, "Серебряные стрелы": 1},
        description="Переплавить серебро и запечатать защитную руну.",
    ),
    Recipe(
        code="phoenix_feather",
        name="Перо феникса",
        rarity="эпическая",
        gold_cost=80,
        ingredients={"Жетон судьбы": 2, "Большое зелье лечения": 1},
        description="Редкий компонент для возвращения героя к жизни.",
    ),
)
RECIPES_BY_CODE = {recipe.code: recipe for recipe in RECIPES}


def item_code(item_name: str) -> str:
    return hashlib.blake2s(item_name.encode("utf-8"), digest_size=5).hexdigest()


def salvage_value(rarity: str) -> int:
    return SALVAGE_VALUES.get(rarity, SALVAGE_VALUES["обычная"])


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS inventory (
            chat_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity >= 0),
            PRIMARY KEY(chat_id, item_name)
        );

        CREATE TABLE IF NOT EXISTS party_wallets (
            chat_id INTEGER PRIMARY KEY,
            gold INTEGER NOT NULL DEFAULT 100 CHECK(gold >= 0)
        );

        CREATE TABLE IF NOT EXISTS forge_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('craft', 'salvage')),
            item_name TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_forge_history_chat_id
        ON forge_history(chat_id, id DESC);
        """
    )


def _wallet(connection: sqlite3.Connection, chat_id: int) -> int:
    connection.execute(
        "INSERT INTO party_wallets(chat_id, gold) VALUES (?, 100) "
        "ON CONFLICT(chat_id) DO NOTHING",
        (chat_id,),
    )
    row = connection.execute(
        "SELECT gold FROM party_wallets WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    return int(row[0]) if row else 100


def _inventory(connection: sqlite3.Connection, chat_id: int) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT item_name, rarity, quantity
        FROM inventory
        WHERE chat_id = ? AND quantity > 0
        ORDER BY
            CASE rarity
                WHEN 'легендарная' THEN 4
                WHEN 'эпическая' THEN 3
                WHEN 'редкая' THEN 2
                ELSE 1
            END DESC,
            item_name
        """,
        (chat_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _missing_for_recipe(inventory: list[dict[str, Any]], recipe: Recipe) -> dict[str, int]:
    quantities = {str(item["item_name"]): int(item["quantity"]) for item in inventory}
    missing: dict[str, int] = {}
    for item_name, required in recipe.ingredients.items():
        absent = required - quantities.get(item_name, 0)
        if absent > 0:
            missing[item_name] = absent
    return missing


def _snapshot(path: Path, chat_id: int) -> ForgeSnapshot:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        gold = _wallet(connection, chat_id)
        inventory = _inventory(connection, chat_id)
        statuses = tuple(
            RecipeStatus(
                recipe=recipe,
                available=not (missing := _missing_for_recipe(inventory, recipe))
                and gold >= recipe.gold_cost,
                missing=missing,
                gold_balance=gold,
            )
            for recipe in RECIPES
        )
        connection.commit()
        return ForgeSnapshot(gold, tuple(inventory), statuses)


def _craft(path: Path, chat_id: int, user_id: int, recipe_code: str) -> CraftResult:
    recipe = RECIPES_BY_CODE.get(recipe_code)
    if recipe is None:
        raise ValueError("Неизвестный рецепт")

    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        gold = _wallet(connection, chat_id)
        inventory = _inventory(connection, chat_id)
        missing = _missing_for_recipe(inventory, recipe)
        if missing or gold < recipe.gold_cost:
            connection.rollback()
            return CraftResult(False, recipe, gold, missing)

        for item_name, required in recipe.ingredients.items():
            row = connection.execute(
                "SELECT quantity FROM inventory WHERE chat_id = ? AND item_name = ?",
                (chat_id, item_name),
            ).fetchone()
            remaining = int(row[0]) - required
            if remaining > 0:
                connection.execute(
                    "UPDATE inventory SET quantity = ? WHERE chat_id = ? AND item_name = ?",
                    (remaining, chat_id, item_name),
                )
            else:
                connection.execute(
                    "DELETE FROM inventory WHERE chat_id = ? AND item_name = ?",
                    (chat_id, item_name),
                )

        connection.execute(
            "UPDATE party_wallets SET gold = gold - ? WHERE chat_id = ?",
            (recipe.gold_cost, chat_id),
        )
        connection.execute(
            """
            INSERT INTO inventory(chat_id, item_name, rarity, quantity)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(chat_id, item_name) DO UPDATE SET
                quantity=inventory.quantity + 1,
                rarity=excluded.rarity
            """,
            (chat_id, recipe.name, recipe.rarity),
        )
        connection.execute(
            """
            INSERT INTO forge_history(chat_id, user_id, action, item_name, details_json, created_at)
            VALUES (?, ?, 'craft', ?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                recipe.name,
                json.dumps(
                    {
                        "recipe": recipe.code,
                        "gold_cost": recipe.gold_cost,
                        "ingredients": recipe.ingredients,
                    },
                    ensure_ascii=False,
                ),
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        balance = _wallet(connection, chat_id)
        connection.commit()
        return CraftResult(True, recipe, balance, {})


def _salvage(path: Path, chat_id: int, user_id: int, code: str) -> SalvageResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        inventory = _inventory(connection, chat_id)
        matches = [item for item in inventory if item_code(str(item["item_name"])) == code]
        if len(matches) != 1:
            balance = _wallet(connection, chat_id)
            connection.rollback()
            return SalvageResult(False, None, None, 0, balance)

        item = matches[0]
        item_name = str(item["item_name"])
        rarity = str(item["rarity"])
        quantity = int(item["quantity"])
        value = salvage_value(rarity)

        if quantity > 1:
            connection.execute(
                "UPDATE inventory SET quantity = quantity - 1 "
                "WHERE chat_id = ? AND item_name = ?",
                (chat_id, item_name),
            )
        else:
            connection.execute(
                "DELETE FROM inventory WHERE chat_id = ? AND item_name = ?",
                (chat_id, item_name),
            )

        _wallet(connection, chat_id)
        connection.execute(
            "UPDATE party_wallets SET gold = gold + ? WHERE chat_id = ?",
            (value, chat_id),
        )
        connection.execute(
            """
            INSERT INTO forge_history(chat_id, user_id, action, item_name, details_json, created_at)
            VALUES (?, ?, 'salvage', ?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                item_name,
                json.dumps({"rarity": rarity, "gold_received": value}, ensure_ascii=False),
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        balance = _wallet(connection, chat_id)
        connection.commit()
        return SalvageResult(True, item_name, rarity, value, balance)


class ForgeStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def snapshot(self, chat_id: int) -> ForgeSnapshot:
        return await asyncio.to_thread(_snapshot, self.path, chat_id)

    async def craft(self, chat_id: int, user_id: int, recipe_code: str) -> CraftResult:
        return await asyncio.to_thread(_craft, self.path, chat_id, user_id, recipe_code)

    async def salvage(self, chat_id: int, user_id: int, code: str) -> SalvageResult:
        return await asyncio.to_thread(_salvage, self.path, chat_id, user_id, code)
