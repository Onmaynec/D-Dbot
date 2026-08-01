from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import aiosqlite

from app.campaign_logic import achievement_candidates, advance_progress


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CampaignProgressStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaign_quests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    giver TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    reward_text TEXT NOT NULL,
                    complication TEXT NOT NULL,
                    faction_name TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    target INTEGER NOT NULL,
                    gold_reward INTEGER NOT NULL,
                    reputation_reward INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS campaign_locations (
                    chat_id INTEGER PRIMARY KEY,
                    location_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS faction_reputation (
                    chat_id INTEGER NOT NULL,
                    faction_name TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(chat_id, faction_name)
                );

                CREATE TABLE IF NOT EXISTS campaign_achievements (
                    chat_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    unlocked_at TEXT NOT NULL,
                    PRIMARY KEY(chat_id, code)
                );

                CREATE TABLE IF NOT EXISTS campaign_stats (
                    chat_id INTEGER PRIMARY KEY,
                    quests_completed INTEGER NOT NULL DEFAULT 0,
                    locations_visited INTEGER NOT NULL DEFAULT 0,
                    quest_steps INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_campaign_quests_chat_status
                    ON campaign_quests(chat_id, status, id DESC);
                """
            )
            await db.commit()
        self._schema_ready = True

    @staticmethod
    def _quest_from_row(row: aiosqlite.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "title": row["title"],
            "giver": row["giver"],
            "goal": row["goal"],
            "reward_text": row["reward_text"],
            "complication": row["complication"],
            "faction_name": row["faction_name"],
            "progress": int(row["progress"]),
            "target": int(row["target"]),
            "gold_reward": int(row["gold_reward"]),
            "reputation_reward": int(row["reputation_reward"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }

    async def add_quest(self, chat_id: int, quest: dict[str, Any]) -> int:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                INSERT INTO campaign_quests(
                    chat_id, title, giver, goal, reward_text, complication, faction_name,
                    progress, target, gold_reward, reputation_reward, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    chat_id,
                    quest["title"],
                    quest["giver"],
                    quest["goal"],
                    quest["reward_text"],
                    quest["complication"],
                    quest["faction_name"],
                    int(quest.get("progress", 0)),
                    int(quest["target"]),
                    int(quest["gold_reward"]),
                    int(quest.get("reputation_reward", 1)),
                    utc_now(),
                ),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def get_quest(self, chat_id: int, quest_id: int) -> dict[str, Any] | None:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT * FROM campaign_quests WHERE chat_id = ? AND id = ?",
                    (chat_id, quest_id),
                )
            ).fetchone()
        return self._quest_from_row(row) if row else None

    async def list_quests(self, chat_id: int, status: str = "active") -> list[dict[str, Any]]:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT * FROM campaign_quests WHERE chat_id = ? AND status = ? ORDER BY id DESC LIMIT 20",
                    (chat_id, status),
                )
            ).fetchall()
        return [self._quest_from_row(row) for row in rows]

    async def advance_quest(self, chat_id: int, quest_id: int, amount: int = 1) -> dict[str, Any] | None:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute(
                    "SELECT * FROM campaign_quests WHERE chat_id = ? AND id = ? AND status = 'active'",
                    (chat_id, quest_id),
                )
            ).fetchone()
            if row is None:
                await db.rollback()
                return None
            old_progress = int(row["progress"])
            new_progress = advance_progress(old_progress, int(row["target"]), amount)
            await db.execute(
                "UPDATE campaign_quests SET progress = ? WHERE chat_id = ? AND id = ?",
                (new_progress, chat_id, quest_id),
            )
            await self._increment_stats(
                db, chat_id, quest_steps=max(0, new_progress - old_progress)
            )
            await db.commit()
        return await self.get_quest(chat_id, quest_id)

    async def complete_quest(self, chat_id: int, quest_id: int) -> dict[str, Any] | None:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute(
                    "SELECT * FROM campaign_quests WHERE chat_id = ? AND id = ? AND status = 'active'",
                    (chat_id, quest_id),
                )
            ).fetchone()
            if row is None or int(row["progress"]) < int(row["target"]):
                await db.rollback()
                return None
            completed_at = utc_now()
            await db.execute(
                "UPDATE campaign_quests SET status = 'completed', completed_at = ? WHERE chat_id = ? AND id = ?",
                (completed_at, chat_id, quest_id),
            )
            await self._increment_stats(db, chat_id, quests_completed=1)
            await db.commit()
        quest = self._quest_from_row(row)
        quest["status"] = "completed"
        quest["completed_at"] = completed_at
        return quest

    async def abandon_quest(self, chat_id: int, quest_id: int) -> bool:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "UPDATE campaign_quests SET status = 'abandoned' WHERE chat_id = ? AND id = ? AND status = 'active'",
                (chat_id, quest_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def save_location(self, chat_id: int, location: dict[str, Any]) -> int:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                """
                INSERT INTO campaign_locations(chat_id, location_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    location_json=excluded.location_json,
                    updated_at=excluded.updated_at
                """,
                (chat_id, json.dumps(location, ensure_ascii=False), utc_now()),
            )
            await self._increment_stats(db, chat_id, locations_visited=1)
            row = await (
                await db.execute(
                    "SELECT locations_visited FROM campaign_stats WHERE chat_id = ?", (chat_id,)
                )
            ).fetchone()
            await db.commit()
        return int(row[0]) if row else 1

    async def get_location(self, chat_id: int) -> dict[str, Any] | None:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            row = await (
                await db.execute(
                    "SELECT location_json FROM campaign_locations WHERE chat_id = ?", (chat_id,)
                )
            ).fetchone()
        return json.loads(row[0]) if row else None

    async def adjust_reputation(self, chat_id: int, faction_name: str, delta: int) -> int:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                """
                INSERT INTO faction_reputation(chat_id, faction_name, score) VALUES (?, ?, ?)
                ON CONFLICT(chat_id, faction_name) DO UPDATE SET
                    score=MIN(10, MAX(-10, faction_reputation.score + excluded.score))
                """,
                (chat_id, faction_name, delta),
            )
            row = await (
                await db.execute(
                    "SELECT score FROM faction_reputation WHERE chat_id = ? AND faction_name = ?",
                    (chat_id, faction_name),
                )
            ).fetchone()
            await db.commit()
        return int(row[0]) if row else 0

    async def get_reputation(
        self, chat_id: int, faction_names: Iterable[str] = ()
    ) -> dict[str, int]:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            rows = await (
                await db.execute(
                    "SELECT faction_name, score FROM faction_reputation WHERE chat_id = ? ORDER BY faction_name",
                    (chat_id,),
                )
            ).fetchall()
        reputation = {str(row[0]): int(row[1]) for row in rows}
        for faction in faction_names:
            reputation.setdefault(faction, 0)
        return reputation

    async def get_stats(self, chat_id: int) -> dict[str, int]:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            await self._increment_stats(db, chat_id)
            row = await (
                await db.execute(
                    "SELECT quests_completed, locations_visited, quest_steps FROM campaign_stats WHERE chat_id = ?",
                    (chat_id,),
                )
            ).fetchone()
            await db.commit()
        return {
            "quests_completed": int(row[0]),
            "locations_visited": int(row[1]),
            "quest_steps": int(row[2]),
        }

    async def refresh_achievements(
        self, chat_id: int, faction_names: Iterable[str] = ()
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        await self.ensure_schema()
        stats = await self.get_stats(chat_id)
        reputation = await self.get_reputation(chat_id, faction_names)
        candidates = achievement_candidates(stats, reputation)
        newly_unlocked: list[dict[str, str]] = []
        async with aiosqlite.connect(self.path) as db:
            for achievement in candidates:
                cursor = await db.execute(
                    """
                    INSERT OR IGNORE INTO campaign_achievements(
                        chat_id, code, title, description, unlocked_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        chat_id,
                        achievement["code"],
                        achievement["title"],
                        achievement["description"],
                        utc_now(),
                    ),
                )
                if cursor.rowcount > 0:
                    newly_unlocked.append(achievement)
            await db.commit()
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT code, title, description, unlocked_at FROM campaign_achievements WHERE chat_id = ? ORDER BY unlocked_at",
                    (chat_id,),
                )
            ).fetchall()
        all_unlocked = [dict(row) for row in rows]
        return all_unlocked, newly_unlocked

    @staticmethod
    async def _increment_stats(
        db: aiosqlite.Connection,
        chat_id: int,
        quests_completed: int = 0,
        locations_visited: int = 0,
        quest_steps: int = 0,
    ) -> None:
        await db.execute(
            """
            INSERT INTO campaign_stats(
                chat_id, quests_completed, locations_visited, quest_steps, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                quests_completed=campaign_stats.quests_completed + excluded.quests_completed,
                locations_visited=campaign_stats.locations_visited + excluded.locations_visited,
                quest_steps=campaign_stats.quest_steps + excluded.quest_steps,
                updated_at=excluded.updated_at
            """,
            (chat_id, quests_completed, locations_visited, quest_steps, utc_now()),
        )
