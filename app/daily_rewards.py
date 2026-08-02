from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

BONUS_ITEMS = (
    ("Зелье лечения", "обычная"),
    ("Большое зелье лечения", "редкая"),
    ("Свиток удачи", "редкая"),
)


@dataclass(frozen=True, slots=True)
class DailyReward:
    gold: int
    item_name: str | None = None
    item_rarity: str | None = None


@dataclass(frozen=True, slots=True)
class DailyStatus:
    claimed_today: bool
    streak: int
    total_claims: int
    next_streak: int
    next_claim_date: date
    preview: DailyReward


@dataclass(frozen=True, slots=True)
class DailyClaimResult:
    claimed: bool
    streak: int
    total_claims: int
    reward: DailyReward | None
    gold_balance: int
    next_claim_date: date


def utc_today() -> date:
    return datetime.now(UTC).date()


def calculate_next_streak(last_claim_date: date | None, current_streak: int, today: date) -> int:
    if last_claim_date == today:
        return max(1, current_streak)
    if last_claim_date == today - timedelta(days=1):
        return max(1, current_streak) + 1
    return 1


def build_daily_reward(chat_id: int, claim_date: date, streak: int) -> DailyReward:
    seed = f"{chat_id}:{claim_date.isoformat()}:{streak}".encode()
    roll = int.from_bytes(hashlib.blake2b(seed, digest_size=8).digest(), "big")
    gold = 20 + min(streak, 14) * 3 + roll % 11
    item_name: str | None = None
    item_rarity: str | None = None

    if streak % 7 == 0:
        gold += 50
        item_name = "Жетон судьбы"
        item_rarity = "эпическая"
    elif streak % 3 == 0:
        item_name, item_rarity = BONUS_ITEMS[roll % len(BONUS_ITEMS)]

    return DailyReward(gold=gold, item_name=item_name, item_rarity=item_rarity)


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS daily_rewards (
            chat_id INTEGER PRIMARY KEY,
            last_claim_date TEXT NOT NULL,
            streak INTEGER NOT NULL CHECK(streak >= 1),
            total_claims INTEGER NOT NULL CHECK(total_claims >= 1),
            claimed_by INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS party_wallets (
            chat_id INTEGER PRIMARY KEY,
            gold INTEGER NOT NULL DEFAULT 100 CHECK(gold >= 0)
        );

        CREATE TABLE IF NOT EXISTS inventory (
            chat_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity >= 0),
            PRIMARY KEY(chat_id, item_name)
        );
        """
    )


def _read_row(connection: sqlite3.Connection, chat_id: int) -> sqlite3.Row | None:
    connection.row_factory = sqlite3.Row
    return connection.execute(
        "SELECT last_claim_date, streak, total_claims FROM daily_rewards WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()


def _status_from_row(chat_id: int, row: sqlite3.Row | None, today: date) -> DailyStatus:
    if row is None:
        return DailyStatus(False, 0, 0, 1, today, build_daily_reward(chat_id, today, 1))

    last_claim = date.fromisoformat(str(row["last_claim_date"]))
    streak = int(row["streak"])
    total_claims = int(row["total_claims"])
    if last_claim == today:
        next_date = today + timedelta(days=1)
        next_streak = streak + 1
        return DailyStatus(
            True,
            streak,
            total_claims,
            next_streak,
            next_date,
            build_daily_reward(chat_id, next_date, next_streak),
        )

    next_streak = calculate_next_streak(last_claim, streak, today)
    active_streak = streak if last_claim == today - timedelta(days=1) else 0
    return DailyStatus(
        False,
        active_streak,
        total_claims,
        next_streak,
        today,
        build_daily_reward(chat_id, today, next_streak),
    )


def _get_status(path: Path, chat_id: int, today: date) -> DailyStatus:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        row = _read_row(connection, chat_id)
        return _status_from_row(chat_id, row, today)


def _claim(path: Path, chat_id: int, user_id: int, today: date) -> DailyClaimResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        row = _read_row(connection, chat_id)
        status = _status_from_row(chat_id, row, today)
        if status.claimed_today:
            wallet = connection.execute(
                "SELECT gold FROM party_wallets WHERE chat_id = ?", (chat_id,)
            ).fetchone()
            connection.rollback()
            return DailyClaimResult(
                False,
                status.streak,
                status.total_claims,
                None,
                int(wallet[0]) if wallet else 100,
                status.next_claim_date,
            )

        reward = status.preview
        total_claims = status.total_claims + 1
        now = datetime.now(UTC).isoformat(timespec="seconds")
        connection.execute(
            """
            INSERT INTO daily_rewards(chat_id, last_claim_date, streak, total_claims, claimed_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                last_claim_date=excluded.last_claim_date,
                streak=excluded.streak,
                total_claims=excluded.total_claims,
                claimed_by=excluded.claimed_by,
                updated_at=excluded.updated_at
            """,
            (chat_id, today.isoformat(), status.next_streak, total_claims, user_id, now),
        )
        connection.execute(
            "INSERT INTO party_wallets(chat_id, gold) VALUES (?, 100) ON CONFLICT(chat_id) DO NOTHING",
            (chat_id,),
        )
        connection.execute(
            "UPDATE party_wallets SET gold = gold + ? WHERE chat_id = ?",
            (reward.gold, chat_id),
        )
        if reward.item_name and reward.item_rarity:
            connection.execute(
                """
                INSERT INTO inventory(chat_id, item_name, rarity, quantity) VALUES (?, ?, ?, 1)
                ON CONFLICT(chat_id, item_name) DO UPDATE SET
                    quantity=inventory.quantity + 1,
                    rarity=excluded.rarity
                """,
                (chat_id, reward.item_name, reward.item_rarity),
            )
        wallet = connection.execute(
            "SELECT gold FROM party_wallets WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        connection.commit()
        return DailyClaimResult(
            True,
            status.next_streak,
            total_claims,
            reward,
            int(wallet[0]),
            today + timedelta(days=1),
        )


class DailyRewardStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def get_status(self, chat_id: int, today: date | None = None) -> DailyStatus:
        return await asyncio.to_thread(_get_status, self.path, chat_id, today or utc_today())

    async def claim(
        self,
        chat_id: int,
        user_id: int,
        today: date | None = None,
    ) -> DailyClaimResult:
        return await asyncio.to_thread(_claim, self.path, chat_id, user_id, today or utc_today())
