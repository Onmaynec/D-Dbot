from __future__ import annotations

import asyncio
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ALLOWED_BETS = (10, 25, 50, 100)
MAX_DAILY_STAKE = 500
RUNE_SYMBOLS = ("☠️", "💎", "⚔️", "🔮", "👑")


@dataclass(frozen=True, slots=True)
class CasinoResult:
    ok: bool
    reason: str
    game: str
    bet: int
    payout: int
    net: int
    balance: int
    title: str
    details: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS party_wallets (
            chat_id INTEGER PRIMARY KEY,
            gold INTEGER NOT NULL DEFAULT 100 CHECK(gold >= 0)
        );

        CREATE TABLE IF NOT EXISTS casino_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            game TEXT NOT NULL,
            bet INTEGER NOT NULL,
            payout INTEGER NOT NULL,
            net INTEGER NOT NULL,
            result_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_casino_history_chat
        ON casino_history(chat_id, id DESC);
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
    return int(row[0]) if row else 0


def _daily_stake(connection: sqlite3.Connection, chat_id: int) -> int:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(bet), 0)
        FROM casino_history
        WHERE chat_id = ? AND substr(created_at, 1, 10) = ?
        """,
        (chat_id, _today()),
    ).fetchone()
    return int(row[0]) if row else 0


def _coin() -> tuple[int, str, str]:
    side = "Орёл" if secrets.randbelow(2) else "Решка"
    won = side == "Орёл"
    return (2 if won else 0), ("Монета благоволит партии" if won else "Монета забирает ставку"), side


def _dice() -> tuple[int, str, str]:
    player = secrets.randbelow(6) + 1
    house = secrets.randbelow(6) + 1
    details = f"Герои: {player} · Крупье: {house}"
    if player > house:
        return 2, "Кости героев сильнее", details
    if player == house:
        return 1, "Ничья — ставка возвращена", details
    return 0, "Крупье выигрывает", details


def _runes() -> tuple[int, str, str]:
    symbols = tuple(secrets.choice(RUNE_SYMBOLS) for _ in range(3))
    details = "  ".join(symbols)
    unique = len(set(symbols))
    if symbols == ("👑", "👑", "👑"):
        return 10, "Королевский джекпот!", details
    if unique == 1:
        return 5, "Тройное совпадение", details
    if unique == 2:
        return 2, "Пара рун", details
    return 0, "Руны молчат", details


def _play(
    path: Path,
    chat_id: int,
    user_id: int,
    game: str,
    bet: int,
) -> CasinoResult:
    if game not in {"coin", "dice", "runes"}:
        return CasinoResult(False, "Неизвестная игра.", game, bet, 0, 0, 0, "", "")
    if bet not in ALLOWED_BETS:
        return CasinoResult(False, "Недопустимая ставка.", game, bet, 0, 0, 0, "", "")

    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        balance = _wallet(connection, chat_id)
        staked = _daily_stake(connection, chat_id)
        if staked + bet > MAX_DAILY_STAKE:
            connection.rollback()
            return CasinoResult(
                False,
                f"Дневной лимит ставок — {MAX_DAILY_STAKE} золота. Сегодня уже поставлено {staked}.",
                game,
                bet,
                0,
                0,
                balance,
                "",
                "",
            )
        if balance < bet:
            connection.rollback()
            return CasinoResult(
                False,
                f"В казне {balance} золота, а ставка требует {bet}.",
                game,
                bet,
                0,
                0,
                balance,
                "",
                "",
            )

        if game == "coin":
            multiplier, title, details = _coin()
        elif game == "dice":
            multiplier, title, details = _dice()
        else:
            multiplier, title, details = _runes()

        payout = bet * multiplier
        net = payout - bet
        balance_after = balance + net
        connection.execute(
            "UPDATE party_wallets SET gold = ? WHERE chat_id = ?",
            (balance_after, chat_id),
        )
        connection.execute(
            """
            INSERT INTO casino_history(
                chat_id, user_id, game, bet, payout, net, result_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (chat_id, user_id, game, bet, payout, net, f"{title}: {details}", _now()),
        )
        connection.commit()
        return CasinoResult(
            True,
            "",
            game,
            bet,
            payout,
            net,
            balance_after,
            title,
            details,
        )


def _status(path: Path, chat_id: int, limit: int = 5) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        balance = _wallet(connection, chat_id)
        staked = _daily_stake(connection, chat_id)
        rows = connection.execute(
            """
            SELECT game, bet, net, result_text, created_at
            FROM casino_history
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_id, max(1, min(10, limit))),
        ).fetchall()
        connection.commit()
    return {
        "balance": balance,
        "daily_stake": staked,
        "daily_limit": MAX_DAILY_STAKE,
        "history": [
            {
                "game": str(row[0]),
                "bet": int(row[1]),
                "net": int(row[2]),
                "result": str(row[3]),
                "created_at": str(row[4]),
            }
            for row in rows
        ],
    }


class CasinoStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def play(self, chat_id: int, user_id: int, game: str, bet: int) -> CasinoResult:
        return await asyncio.to_thread(_play, self.path, chat_id, user_id, game, bet)

    async def status(self, chat_id: int, limit: int = 5) -> dict[str, Any]:
        return await asyncio.to_thread(_status, self.path, chat_id, limit)
