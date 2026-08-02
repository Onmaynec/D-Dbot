import asyncio
import sqlite3
from pathlib import Path

from app.maintenance import check_database, create_database_backup, format_bytes


def create_source_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE heroes(name TEXT NOT NULL)")
        connection.execute("INSERT INTO heroes(name) VALUES ('Арден')")
        connection.commit()


def test_backup_is_consistent_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "campaign.sqlite3"
    backup_dir = tmp_path / "backups"
    create_source_database(source)

    backup = asyncio.run(create_database_backup(source, backup_dir, keep=3))

    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO heroes(name) VALUES ('Мира')")
        connection.commit()
    with sqlite3.connect(backup) as connection:
        heroes = connection.execute("SELECT name FROM heroes ORDER BY name").fetchall()

    assert heroes == [("Арден",)]
    assert asyncio.run(check_database(backup)).ok is True


def test_backup_rotation_keeps_requested_count(tmp_path: Path) -> None:
    source = tmp_path / "campaign.sqlite3"
    backup_dir = tmp_path / "backups"
    create_source_database(source)

    for _ in range(4):
        asyncio.run(create_database_backup(source, backup_dir, keep=2))

    assert len(list(backup_dir.glob("campaign-*.sqlite3"))) == 2


def test_health_reports_missing_database(tmp_path: Path) -> None:
    health = asyncio.run(check_database(tmp_path / "missing.sqlite3"))

    assert health.ok is False
    assert "не найден" in health.message


def test_format_bytes() -> None:
    assert format_bytes(512) == "512 Б"
    assert format_bytes(2048) == "2.0 КБ"
