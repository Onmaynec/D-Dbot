from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _apply(path: Path, chat_id: int) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS v5_chat_migrations (
                chat_id INTEGER PRIMARY KEY,
                hq_images_enabled INTEGER NOT NULL DEFAULT 0,
                migrated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_game_settings (
                chat_id INTEGER PRIMARY KEY,
                difficulty TEXT NOT NULL DEFAULT 'normal',
                image_mode TEXT NOT NULL DEFAULT 'document',
                updated_at TEXT NOT NULL
            );
            """
        )
        row = connection.execute(
            "SELECT hq_images_enabled FROM v5_chat_migrations WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if row is not None and int(row[0]) == 1:
            connection.commit()
            return False
        connection.execute(
            """
            INSERT INTO chat_game_settings(chat_id, difficulty, image_mode, updated_at)
            VALUES (?, 'normal', 'document', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                image_mode='document',
                updated_at=excluded.updated_at
            """,
            (chat_id, _now()),
        )
        connection.execute(
            """
            INSERT INTO v5_chat_migrations(chat_id, hq_images_enabled, migrated_at)
            VALUES (?, 1, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                hq_images_enabled=1,
                migrated_at=excluded.migrated_at
            """,
            (chat_id, _now()),
        )
        connection.commit()
        return True


async def apply_v5_chat_defaults(path: Path, chat_id: int) -> bool:
    """Один раз включает PNG без сжатия, после чего пользователь снова может менять режим."""
    return await asyncio.to_thread(_apply, path, chat_id)
