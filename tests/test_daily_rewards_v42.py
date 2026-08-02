import asyncio
import sqlite3
from datetime import date
from pathlib import Path

from app.daily_rewards import DailyRewardStore, build_daily_reward, calculate_next_streak


def test_streak_continues_or_resets() -> None:
    assert calculate_next_streak(date(2026, 8, 1), 4, date(2026, 8, 2)) == 5
    assert calculate_next_streak(date(2026, 7, 30), 4, date(2026, 8, 2)) == 1


def test_reward_is_deterministic_and_has_seventh_day_bonus() -> None:
    first = build_daily_reward(42, date(2026, 8, 2), 7)
    second = build_daily_reward(42, date(2026, 8, 2), 7)

    assert first == second
    assert first.item_name == "Жетон судьбы"
    assert first.item_rarity == "эпическая"
    assert first.gold >= 90


def test_claim_is_atomic_and_cannot_be_repeated(tmp_path: Path) -> None:
    database = tmp_path / "daily.sqlite3"
    store = DailyRewardStore(database)

    first = asyncio.run(store.claim(100, 10, date(2026, 8, 1)))
    duplicate = asyncio.run(store.claim(100, 11, date(2026, 8, 1)))

    assert first.claimed is True
    assert duplicate.claimed is False
    assert duplicate.gold_balance == first.gold_balance
    with sqlite3.connect(database) as connection:
        total_claims = connection.execute(
            "SELECT total_claims FROM daily_rewards WHERE chat_id = 100"
        ).fetchone()[0]
    assert total_claims == 1


def test_consecutive_claims_add_bonus_item_and_missed_day_resets(tmp_path: Path) -> None:
    database = tmp_path / "daily.sqlite3"
    store = DailyRewardStore(database)

    asyncio.run(store.claim(200, 10, date(2026, 8, 1)))
    second = asyncio.run(store.claim(200, 10, date(2026, 8, 2)))
    third = asyncio.run(store.claim(200, 10, date(2026, 8, 3)))
    reset = asyncio.run(store.claim(200, 10, date(2026, 8, 6)))

    assert second.streak == 2
    assert third.streak == 3
    assert third.reward is not None and third.reward.item_name is not None
    assert reset.streak == 1
    with sqlite3.connect(database) as connection:
        item = connection.execute(
            "SELECT quantity FROM inventory WHERE chat_id = 200 AND item_name = ?",
            (third.reward.item_name,),
        ).fetchone()
    assert item == (1,)
