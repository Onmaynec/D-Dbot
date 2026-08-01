from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS campaigns (
                    chat_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    world_name TEXT NOT NULL,
                    world_type TEXT NOT NULL,
                    factions_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    campaign_name TEXT,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    campaign_name TEXT,
                    event_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS combats (
                    chat_id INTEGER PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS party_members (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    character_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(chat_id, user_id)
                );

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

                CREATE INDEX IF NOT EXISTS idx_journal_chat_id ON journal(chat_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_characters_chat_id ON characters(chat_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_party_members_chat_id ON party_members(chat_id);
                """
            )
            await db.commit()

    async def save_campaign(self, chat_id: int, campaign: dict[str, Any]) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO campaigns(chat_id, name, world_name, world_type, factions_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    name=excluded.name,
                    world_name=excluded.world_name,
                    world_type=excluded.world_type,
                    factions_json=excluded.factions_json,
                    created_at=excluded.created_at
                """,
                (
                    chat_id,
                    campaign["name"],
                    campaign["world_name"],
                    campaign["world_type"],
                    json.dumps(campaign["factions"], ensure_ascii=False),
                    utc_now(),
                ),
            )
            await db.commit()

    async def get_campaign(self, chat_id: int) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            row = await (await db.execute("SELECT * FROM campaigns WHERE chat_id = ?", (chat_id,))).fetchone()
        if row is None:
            return None
        return {
            "name": row["name"],
            "world_name": row["world_name"],
            "world_type": row["world_type"],
            "factions": json.loads(row["factions_json"]),
        }

    async def add_character(self, chat_id: int, campaign_name: str | None, character: dict[str, Any]) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "INSERT INTO characters(chat_id, campaign_name, data_json, created_at) VALUES (?, ?, ?, ?)",
                (chat_id, campaign_name, json.dumps(character, ensure_ascii=False), utc_now()),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def get_active_character(self, chat_id: int) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT id, data_json FROM characters WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
                    (chat_id,),
                )
            ).fetchone()
        if row is None:
            return None
        data = json.loads(row["data_json"])
        data["id"] = row["id"]
        return data

    async def update_character(self, character: dict[str, Any]) -> None:
        character_id = int(character["id"])
        payload = {key: value for key, value in character.items() if key != "id"}
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE characters SET data_json = ? WHERE id = ?",
                (json.dumps(payload, ensure_ascii=False), character_id),
            )
            await db.commit()

    async def add_journal(self, chat_id: int, campaign_name: str | None, event_type: str, content: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO journal(chat_id, campaign_name, event_type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (chat_id, campaign_name, event_type, content, utc_now()),
            )
            await db.commit()

    async def get_journal(self, chat_id: int, limit: int = 30) -> list[dict[str, str]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT event_type, content, created_at FROM journal WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
                    (chat_id, limit),
                )
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    async def save_combat(self, chat_id: int, state: dict[str, Any]) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO combats(chat_id, state_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at
                """,
                (chat_id, json.dumps(state, ensure_ascii=False), utc_now()),
            )
            await db.commit()

    async def get_combat(self, chat_id: int) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.path) as db:
            row = await (await db.execute("SELECT state_json FROM combats WHERE chat_id = ?", (chat_id,))).fetchone()
        return json.loads(row[0]) if row else None

    async def clear_combat(self, chat_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM combats WHERE chat_id = ?", (chat_id,))
            await db.commit()

    async def get_party_member(self, chat_id: int, user_id: int) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT user_id, display_name, character_json FROM party_members WHERE chat_id = ? AND user_id = ?",
                    (chat_id, user_id),
                )
            ).fetchone()
        if row is None:
            return None
        return {
            "user_id": int(row["user_id"]),
            "display_name": row["display_name"],
            "character": json.loads(row["character_json"]),
        }

    async def upsert_party_member(
        self, chat_id: int, user_id: int, display_name: str, character: dict[str, Any]
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO party_members(chat_id, user_id, display_name, character_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    character_json=excluded.character_json
                """,
                (chat_id, user_id, display_name, json.dumps(character, ensure_ascii=False), utc_now()),
            )
            await db.commit()

    async def get_party_members(self, chat_id: int) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT user_id, display_name, character_json FROM party_members WHERE chat_id = ? ORDER BY created_at",
                    (chat_id,),
                )
            ).fetchall()
        return [
            {
                "user_id": int(row["user_id"]),
                "display_name": row["display_name"],
                "character": json.loads(row["character_json"]),
            }
            for row in rows
        ]

    async def remove_party_member(self, chat_id: int, user_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "DELETE FROM party_members WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_inventory(self, chat_id: int) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT item_name, rarity, quantity FROM inventory WHERE chat_id = ? AND quantity > 0 ORDER BY rarity, item_name",
                    (chat_id,),
                )
            ).fetchall()
        return [dict(row) for row in rows]

    async def add_inventory_item(
        self, chat_id: int, item_name: str, rarity: str = "обычная", quantity: int = 1
    ) -> None:
        if quantity <= 0:
            raise ValueError("Количество предметов должно быть положительным")
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO inventory(chat_id, item_name, rarity, quantity) VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id, item_name) DO UPDATE SET
                    quantity=inventory.quantity + excluded.quantity,
                    rarity=excluded.rarity
                """,
                (chat_id, item_name, rarity, quantity),
            )
            await db.commit()

    async def consume_inventory_item(self, chat_id: int, item_name: str, quantity: int = 1) -> bool:
        if quantity <= 0:
            return False
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute(
                    "SELECT quantity FROM inventory WHERE chat_id = ? AND item_name = ?",
                    (chat_id, item_name),
                )
            ).fetchone()
            if row is None or int(row[0]) < quantity:
                await db.rollback()
                return False
            remaining = int(row[0]) - quantity
            if remaining:
                await db.execute(
                    "UPDATE inventory SET quantity = ? WHERE chat_id = ? AND item_name = ?",
                    (remaining, chat_id, item_name),
                )
            else:
                await db.execute(
                    "DELETE FROM inventory WHERE chat_id = ? AND item_name = ?",
                    (chat_id, item_name),
                )
            await db.commit()
            return True

    async def get_gold(self, chat_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO party_wallets(chat_id, gold) VALUES (?, 100) ON CONFLICT(chat_id) DO NOTHING",
                (chat_id,),
            )
            row = await (await db.execute("SELECT gold FROM party_wallets WHERE chat_id = ?", (chat_id,))).fetchone()
            await db.commit()
        return int(row[0]) if row else 100

    async def add_gold(self, chat_id: int, amount: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                "INSERT INTO party_wallets(chat_id, gold) VALUES (?, 100) ON CONFLICT(chat_id) DO NOTHING",
                (chat_id,),
            )
            await db.execute(
                "UPDATE party_wallets SET gold = MAX(0, gold + ?) WHERE chat_id = ?", (amount, chat_id)
            )
            row = await (await db.execute("SELECT gold FROM party_wallets WHERE chat_id = ?", (chat_id,))).fetchone()
            await db.commit()
        return int(row[0])

    async def try_spend_gold(self, chat_id: int, amount: int) -> tuple[bool, int]:
        if amount <= 0:
            return True, await self.get_gold(chat_id)
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                "INSERT INTO party_wallets(chat_id, gold) VALUES (?, 100) ON CONFLICT(chat_id) DO NOTHING",
                (chat_id,),
            )
            row = await (await db.execute("SELECT gold FROM party_wallets WHERE chat_id = ?", (chat_id,))).fetchone()
            current = int(row[0])
            if current < amount:
                await db.rollback()
                return False, current
            remaining = current - amount
            await db.execute("UPDATE party_wallets SET gold = ? WHERE chat_id = ?", (remaining, chat_id))
            await db.commit()
            return True, remaining
