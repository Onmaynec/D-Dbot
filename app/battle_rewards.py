from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOOT_BY_TIER: dict[int, tuple[tuple[str, str], ...]] = {
    1: (("Зелье лечения", "обычная"),),
    2: (
        ("Зелье лечения", "обычная"),
        ("Серебряные стрелы", "редкая"),
    ),
    3: (
        ("Большое зелье лечения", "редкая"),
        ("Свиток удачи", "редкая"),
        ("Серебряные стрелы", "редкая"),
    ),
    4: (
        ("Большое зелье лечения", "редкая"),
        ("Свиток удачи", "редкая"),
        ("Жетон судьбы", "эпическая"),
    ),
    5: (
        ("Жетон судьбы", "эпическая"),
        ("Перо феникса", "эпическая"),
        ("Свиток удачи", "редкая"),
    ),
}


@dataclass(frozen=True, slots=True)
class BattleReward:
    battle_id: str
    xp_each: int
    gold: int
    item_name: str
    rarity: str
    quantity: int
    party_size: int
    total_enemy_xp: int


def ensure_battle_id(state: dict[str, Any]) -> str:
    value = str(state.get("battle_id", "")).strip()
    if not value:
        value = uuid.uuid4().hex
        state["battle_id"] = value
    return value


def _fallback_battle_id(state: dict[str, Any]) -> str:
    payload = json.dumps(state, ensure_ascii=False, sort_keys=True)
    return hashlib.blake2s(payload.encode("utf-8"), digest_size=12).hexdigest()


def calculate_battle_reward(state: dict[str, Any]) -> BattleReward:
    party = [
        member
        for member in state.get("party", [])
        if isinstance(member.get("character"), dict)
    ]
    party_size = max(1, len(party))
    enemies = list(state.get("enemies", []))
    total_enemy_xp = sum(max(0, int(enemy.get("xp", 0))) for enemy in enemies)
    xp_each = max(10, (total_enemy_xp + party_size - 1) // party_size)

    level = max(1, int(state.get("party_level", 1)))
    rounds = max(1, int(state.get("round", 1)))
    gold = max(12, level * 10 + len(enemies) * 7 + min(rounds, 10) * 2)

    tier = min(5, level)
    candidates = LOOT_BY_TIER[tier]
    index = (total_enemy_xp + rounds + party_size) % len(candidates)
    item_name, rarity = candidates[index]
    battle_id = str(state.get("battle_id", "")).strip() or _fallback_battle_id(state)

    return BattleReward(
        battle_id=battle_id,
        xp_each=xp_each,
        gold=gold,
        item_name=item_name,
        rarity=rarity,
        quantity=1,
        party_size=party_size,
        total_enemy_xp=total_enemy_xp,
    )


def ensure_reward_schema(connection: sqlite3.Connection) -> None:
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

        CREATE TABLE IF NOT EXISTS battle_reward_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            battle_id TEXT NOT NULL,
            party_size INTEGER NOT NULL,
            total_enemy_xp INTEGER NOT NULL,
            xp_each INTEGER NOT NULL,
            gold INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(chat_id, battle_id)
        );

        CREATE INDEX IF NOT EXISTS idx_battle_reward_history_chat_id
        ON battle_reward_history(chat_id, id DESC);
        """
    )


def grant_battle_reward(
    connection: sqlite3.Connection,
    chat_id: int,
    state: dict[str, Any],
) -> BattleReward:
    ensure_reward_schema(connection)
    ensure_battle_id(state)
    reward = calculate_battle_reward(state)

    inserted = connection.execute(
        """
        INSERT OR IGNORE INTO battle_reward_history(
            chat_id,
            battle_id,
            party_size,
            total_enemy_xp,
            xp_each,
            gold,
            item_name,
            rarity,
            quantity,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chat_id,
            reward.battle_id,
            reward.party_size,
            reward.total_enemy_xp,
            reward.xp_each,
            reward.gold,
            reward.item_name,
            reward.rarity,
            reward.quantity,
            datetime.now(UTC).isoformat(timespec="seconds"),
        ),
    )
    if inserted.rowcount == 0:
        return reward

    for member in state.get("party", []):
        character = member.get("character")
        if isinstance(character, dict):
            character["xp"] = int(character.get("xp", 0)) + reward.xp_each

    connection.execute(
        """
        INSERT INTO party_wallets(chat_id, gold)
        VALUES (?, 100)
        ON CONFLICT(chat_id) DO NOTHING
        """,
        (chat_id,),
    )
    connection.execute(
        "UPDATE party_wallets SET gold = gold + ? WHERE chat_id = ?",
        (reward.gold, chat_id),
    )
    connection.execute(
        """
        INSERT INTO inventory(chat_id, item_name, rarity, quantity)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chat_id, item_name) DO UPDATE SET
            quantity=inventory.quantity + excluded.quantity,
            rarity=excluded.rarity
        """,
        (
            chat_id,
            reward.item_name,
            reward.rarity,
            reward.quantity,
        ),
    )
    return reward


def list_recent_rewards(
    path: str | Path,
    chat_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    with sqlite3.connect(path) as connection:
        ensure_reward_schema(connection)
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT battle_id, party_size, total_enemy_xp, xp_each, gold,
                   item_name, rarity, quantity, created_at
            FROM battle_reward_history
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_id, max(1, min(20, int(limit)))),
        ).fetchall()
    return [dict(row) for row in rows]


class BattleRewardStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def recent(
        self,
        chat_id: int,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            list_recent_rewards,
            self.path,
            chat_id,
            limit,
        )
