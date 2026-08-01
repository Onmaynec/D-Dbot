from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


DUNGEON_ACHIEVEMENTS = (
    ("first_descent", "Первый спуск", "Начать первую экспедицию", 1, "runs_started"),
    ("deep_delver", "Исследователь глубин", "Исследовать 10 комнат", 10, "rooms_explored"),
    ("boss_slayer", "Убийца боссов", "Победить первого босса", 1, "bosses_defeated"),
    ("dungeon_master", "Хозяин подземелий", "Победить 5 боссов", 5, "bosses_defeated"),
    ("survivor", "Знающий меру", "Отступить и сохранить жизнь", 1, "retreats"),
)


class DungeonStore:
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
                CREATE TABLE IF NOT EXISTS dungeon_runs (
                    chat_id INTEGER PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dungeon_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    dungeon_name TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    rooms_cleared INTEGER NOT NULL,
                    gold_reward INTEGER NOT NULL DEFAULT 0,
                    completed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_game_settings (
                    chat_id INTEGER PRIMARY KEY,
                    difficulty TEXT NOT NULL DEFAULT 'normal',
                    image_mode TEXT NOT NULL DEFAULT 'photo',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dungeon_stats (
                    chat_id INTEGER PRIMARY KEY,
                    runs_started INTEGER NOT NULL DEFAULT 0,
                    rooms_explored INTEGER NOT NULL DEFAULT 0,
                    bosses_defeated INTEGER NOT NULL DEFAULT 0,
                    retreats INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dungeon_achievements (
                    chat_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    unlocked_at TEXT NOT NULL,
                    PRIMARY KEY(chat_id, code)
                );
                """
            )
            await db.commit()
        self._schema_ready = True

    async def get_settings(self, chat_id: int) -> dict[str, str]:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO chat_game_settings(chat_id, difficulty, image_mode, updated_at)
                VALUES (?, 'normal', 'photo', ?)
                ON CONFLICT(chat_id) DO NOTHING
                """,
                (chat_id, utc_now()),
            )
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT difficulty, image_mode FROM chat_game_settings WHERE chat_id = ?", (chat_id,)
                )
            ).fetchone()
            await db.commit()
        return {"difficulty": str(row["difficulty"]), "image_mode": str(row["image_mode"])}

    async def get_image_mode(self, chat_id: int) -> str:
        return (await self.get_settings(chat_id))["image_mode"]

    async def set_difficulty(self, chat_id: int, difficulty: str) -> None:
        if difficulty not in {"easy", "normal", "hard"}:
            raise ValueError("Неизвестная сложность")
        await self.ensure_schema()
        await self.get_settings(chat_id)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE chat_game_settings SET difficulty = ?, updated_at = ? WHERE chat_id = ?",
                (difficulty, utc_now(), chat_id),
            )
            await db.commit()

    async def set_image_mode(self, chat_id: int, image_mode: str) -> None:
        if image_mode not in {"photo", "document"}:
            raise ValueError("Неизвестный режим изображений")
        await self.ensure_schema()
        await self.get_settings(chat_id)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE chat_game_settings SET image_mode = ?, updated_at = ? WHERE chat_id = ?",
                (image_mode, utc_now(), chat_id),
            )
            await db.commit()

    async def get_run(self, chat_id: int) -> dict[str, Any] | None:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            row = await (
                await db.execute("SELECT state_json FROM dungeon_runs WHERE chat_id = ?", (chat_id,))
            ).fetchone()
        return json.loads(row[0]) if row else None

    async def start_run(self, chat_id: int, state: dict[str, Any]) -> None:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                """
                INSERT INTO dungeon_runs(chat_id, state_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at
                """,
                (chat_id, json.dumps(state, ensure_ascii=False), utc_now()),
            )
            await self._increment_stats(db, chat_id, runs_started=1)
            await db.commit()

    async def save_run(self, chat_id: int, state: dict[str, Any], room_explored: bool = False) -> None:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                """
                INSERT INTO dungeon_runs(chat_id, state_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at
                """,
                (chat_id, json.dumps(state, ensure_ascii=False), utc_now()),
            )
            if room_explored:
                await self._increment_stats(db, chat_id, rooms_explored=1)
            await db.commit()

    async def finish_run(
        self, chat_id: int, state: dict[str, Any], outcome: str, gold_reward: int = 0
    ) -> list[dict[str, str]]:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                """
                INSERT INTO dungeon_history(
                    chat_id, dungeon_name, difficulty, outcome, rooms_cleared, gold_reward, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    str(state.get("name", "Безымянное подземелье")),
                    str(state.get("difficulty", "normal")),
                    outcome,
                    int(state.get("depth", 0)),
                    max(0, int(gold_reward)),
                    utc_now(),
                ),
            )
            await db.execute("DELETE FROM dungeon_runs WHERE chat_id = ?", (chat_id,))
            if outcome == "victory":
                await self._increment_stats(db, chat_id, bosses_defeated=1)
            elif outcome == "retreat":
                await self._increment_stats(db, chat_id, retreats=1)
            await db.commit()
        return await self.refresh_achievements(chat_id)

    async def get_stats(self, chat_id: int) -> dict[str, int]:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute("SELECT * FROM dungeon_stats WHERE chat_id = ?", (chat_id,))
            ).fetchone()
        if row is None:
            return {"runs_started": 0, "rooms_explored": 0, "bosses_defeated": 0, "retreats": 0}
        return {
            "runs_started": int(row["runs_started"]),
            "rooms_explored": int(row["rooms_explored"]),
            "bosses_defeated": int(row["bosses_defeated"]),
            "retreats": int(row["retreats"]),
        }

    async def list_achievements(self, chat_id: int) -> list[dict[str, str]]:
        await self.ensure_schema()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT code, title, description, unlocked_at FROM dungeon_achievements "
                    "WHERE chat_id = ? ORDER BY unlocked_at",
                    (chat_id,),
                )
            ).fetchall()
        return [dict(row) for row in rows]

    async def refresh_achievements(self, chat_id: int) -> list[dict[str, str]]:
        stats = await self.get_stats(chat_id)
        unlocked: list[dict[str, str]] = []
        async with aiosqlite.connect(self.path) as db:
            for code, title, description, threshold, field in DUNGEON_ACHIEVEMENTS:
                if stats[field] < threshold:
                    continue
                cursor = await db.execute(
                    """
                    INSERT OR IGNORE INTO dungeon_achievements(chat_id, code, title, description, unlocked_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (chat_id, code, title, description, utc_now()),
                )
                if cursor.rowcount:
                    unlocked.append({"code": code, "title": title, "description": description})
            await db.commit()
        return unlocked

    @staticmethod
    async def _increment_stats(db: aiosqlite.Connection, chat_id: int, **increments: int) -> None:
        await db.execute(
            """
            INSERT INTO dungeon_stats(chat_id, updated_at) VALUES (?, ?)
            ON CONFLICT(chat_id) DO NOTHING
            """,
            (chat_id, utc_now()),
        )
        for field, amount in increments.items():
            if field not in {"runs_started", "rooms_explored", "bosses_defeated", "retreats"}:
                continue
            await db.execute(
                f"UPDATE dungeon_stats SET {field} = {field} + ?, updated_at = ? WHERE chat_id = ?",
                (int(amount), utc_now(), chat_id),
            )
