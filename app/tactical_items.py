from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SHIELD_SCROLL = "Свиток щита"
PHOENIX_FEATHER = "Перо феникса"
SHIELD_AC_BONUS = 2
SHIELD_DURATION = 2
TACTICAL_ITEMS_BY_CODE = {
    "shield": SHIELD_SCROLL,
    "phoenix": PHOENIX_FEATHER,
}


@dataclass(frozen=True, slots=True)
class TacticalActivationResult:
    activated: bool
    item_name: str
    state: dict[str, Any] | None
    remaining: int
    reason: str


def has_living_enemies(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    return any(
        bool(enemy.get("alive", True)) and int(enemy.get("hp", 0)) > 0
        for enemy in state.get("enemies", [])
    )


def armor_bonus(state: dict[str, Any]) -> int:
    return SHIELD_AC_BONUS if int(state.get("shield_rounds", 0)) > 0 else 0


def advance_shield(state: dict[str, Any]) -> bool:
    rounds = int(state.get("shield_rounds", 0))
    if rounds <= 0:
        state.pop("shield_rounds", None)
        return False
    rounds -= 1
    if rounds <= 0:
        state.pop("shield_rounds", None)
        return True
    state["shield_rounds"] = rounds
    return False


def trigger_phoenix(state: dict[str, Any], max_hp: int) -> int | None:
    if not bool(state.get("phoenix_ready", False)):
        return None
    state.pop("phoenix_ready", None)
    state["phoenix_uses"] = int(state.get("phoenix_uses", 0)) + 1
    return max(1, int(max_hp) // 2)


def combat_effects_text(state: dict[str, Any]) -> str:
    effects: list[str] = []
    rounds = int(state.get("shield_rounds", 0))
    if rounds > 0:
        effects.append(f"🛡️ Защитная руна: +{SHIELD_AC_BONUS} КД, ходов врагов: {rounds}")
    if bool(state.get("phoenix_ready", False)):
        effects.append("🔥 Перо феникса: готово вернуть героя с половиной HP")
    return "\n".join(effects)


def _apply_effect(state: dict[str, Any], item_name: str) -> None:
    if not has_living_enemies(state):
        raise ValueError("Нет активного боя")
    if item_name == SHIELD_SCROLL:
        if int(state.get("shield_rounds", 0)) > 0:
            raise ValueError("Защитная руна уже действует")
        state["shield_rounds"] = SHIELD_DURATION
        return
    if item_name == PHOENIX_FEATHER:
        if bool(state.get("phoenix_ready", False)):
            raise ValueError("Перо феникса уже подготовлено")
        state["phoenix_ready"] = True
        return
    raise ValueError("Неизвестный боевой предмет")


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS combats (
            chat_id INTEGER PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inventory (
            chat_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity >= 0),
            PRIMARY KEY(chat_id, item_name)
        );

        CREATE TABLE IF NOT EXISTS combat_item_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            effect_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_combat_item_history_chat_id
        ON combat_item_history(chat_id, id DESC);
        """
    )


def _remaining(connection: sqlite3.Connection, chat_id: int, item_name: str) -> int:
    row = connection.execute(
        "SELECT quantity FROM inventory WHERE chat_id = ? AND item_name = ?",
        (chat_id, item_name),
    ).fetchone()
    return int(row[0]) if row else 0


def _activate(
    path: Path,
    chat_id: int,
    user_id: int,
    item_code: str,
) -> TacticalActivationResult:
    item_name = TACTICAL_ITEMS_BY_CODE.get(item_code)
    if item_name is None:
        raise ValueError("Неизвестный боевой предмет")

    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT state_json FROM combats WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if row is None:
            connection.rollback()
            return TacticalActivationResult(False, item_name, None, 0, "Сейчас нет активного боя")

        state = json.loads(str(row[0]))
        quantity = _remaining(connection, chat_id, item_name)
        if quantity < 1:
            connection.rollback()
            return TacticalActivationResult(False, item_name, state, 0, "Предмета нет в инвентаре")

        try:
            _apply_effect(state, item_name)
        except ValueError as error:
            connection.rollback()
            return TacticalActivationResult(False, item_name, state, quantity, str(error))

        if quantity > 1:
            connection.execute(
                "UPDATE inventory SET quantity = quantity - 1 "
                "WHERE chat_id = ? AND item_name = ?",
                (chat_id, item_name),
            )
        else:
            connection.execute(
                "DELETE FROM inventory WHERE chat_id = ? AND item_name = ?",
                (chat_id, item_name),
            )

        now = datetime.now(UTC).isoformat(timespec="seconds")
        connection.execute(
            "UPDATE combats SET state_json = ?, updated_at = ? WHERE chat_id = ?",
            (json.dumps(state, ensure_ascii=False), now, chat_id),
        )
        connection.execute(
            """
            INSERT INTO combat_item_history(chat_id, user_id, item_name, effect_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                item_name,
                json.dumps(
                    {
                        "shield_rounds": state.get("shield_rounds", 0),
                        "phoenix_ready": bool(state.get("phoenix_ready", False)),
                    },
                    ensure_ascii=False,
                ),
                now,
            ),
        )
        remaining = _remaining(connection, chat_id, item_name)
        connection.commit()
        return TacticalActivationResult(True, item_name, state, remaining, "Предмет активирован")


class TacticalItemStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def activate(
        self,
        chat_id: int,
        user_id: int,
        item_code: str,
    ) -> TacticalActivationResult:
        return await asyncio.to_thread(_activate, self.path, chat_id, user_id, item_code)
