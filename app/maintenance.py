from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DatabaseHealth:
    ok: bool
    message: str
    size_bytes: int = 0


def format_bytes(size_bytes: int) -> str:
    value = float(max(0, size_bytes))
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024 or unit == "ГБ":
            return f"{value:.0f} {unit}" if unit == "Б" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} ГБ"


def _check_database(path: Path) -> DatabaseHealth:
    if not path.exists():
        return DatabaseHealth(False, "файл базы не найден")

    size_bytes = path.stat().st_size
    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as error:
        return DatabaseHealth(False, f"ошибка SQLite: {error}", size_bytes)

    result = str(row[0]) if row else "нет ответа"
    if result.lower() != "ok":
        return DatabaseHealth(False, result, size_bytes)
    return DatabaseHealth(True, "целостность подтверждена", size_bytes)


async def check_database(path: Path) -> DatabaseHealth:
    return await asyncio.to_thread(_check_database, path)


def _create_database_backup(source: Path, backup_dir: Path, keep: int) -> Path:
    if keep < 1:
        raise ValueError("BACKUP_KEEP должен быть не меньше 1")
    if not source.exists():
        raise FileNotFoundError(source)

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    destination = backup_dir / f"{source.stem}-{timestamp}.sqlite3"

    try:
        with sqlite3.connect(source) as source_db, sqlite3.connect(destination) as destination_db:
            source_db.backup(destination_db)

        health = _check_database(destination)
        if not health.ok:
            raise sqlite3.DatabaseError(f"резервная копия повреждена: {health.message}")
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    backups = sorted(
        backup_dir.glob(f"{source.stem}-*.sqlite3"),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    for old_backup in backups[keep:]:
        old_backup.unlink(missing_ok=True)

    return destination


async def create_database_backup(source: Path, backup_dir: Path, keep: int = 7) -> Path:
    return await asyncio.to_thread(_create_database_backup, source, backup_dir, keep)
