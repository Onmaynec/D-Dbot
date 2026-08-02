from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.combat import living_enemies
from app.gameplay import use_healing_item
from app.party_combat import (
    action_guard,
    mark_acted,
    party_member,
    resolve_party_enemy_phase,
    round_ready,
)

HEALING_ITEMS_BY_CODE = {
    "small": "Зелье лечения",
    "greater": "Большое зелье лечения",
}


@dataclass(frozen=True, slots=True)
class SupportActionResult:
    allowed: bool
    reason: str
    state: dict[str, Any] | None
    actor: dict[str, Any] | None
    target: dict[str, Any] | None
    item_name: str | None
    rolled: int
    restored: int
    remaining: int
    enemy_events: tuple[dict[str, Any], ...]
    round_complete: bool
    defeat: bool
    shield_expired: bool


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS party_support_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            target_user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            restored_hp INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_party_support_history_chat_id
        ON party_support_history(chat_id, id DESC);
        """
    )


def _load_state(
    connection: sqlite3.Connection,
    chat_id: int,
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT state_json FROM combats WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    return json.loads(row[0]) if row else None


def _write_state(
    connection: sqlite3.Connection,
    chat_id: int,
    state: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO combats(chat_id, state_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            state_json=excluded.state_json,
            updated_at=excluded.updated_at
        """,
        (
            chat_id,
            json.dumps(state, ensure_ascii=False),
            datetime.now(UTC).isoformat(timespec="seconds"),
        ),
    )


def _write_party(
    connection: sqlite3.Connection,
    chat_id: int,
    state: dict[str, Any],
) -> None:
    for member in state.get("party", []):
        connection.execute(
            """
            UPDATE party_members
            SET display_name = ?, character_json = ?
            WHERE chat_id = ? AND user_id = ?
            """,
            (
                str(member["display_name"]),
                json.dumps(member["character"], ensure_ascii=False),
                chat_id,
                int(member["user_id"]),
            ),
        )


def _consume_item(
    connection: sqlite3.Connection,
    chat_id: int,
    item_name: str,
) -> int | None:
    row = connection.execute(
        """
        SELECT quantity
        FROM inventory
        WHERE chat_id = ? AND item_name = ?
        """,
        (chat_id, item_name),
    ).fetchone()
    if row is None or int(row[0]) <= 0:
        return None

    remaining = int(row[0]) - 1
    if remaining:
        connection.execute(
            """
            UPDATE inventory
            SET quantity = ?
            WHERE chat_id = ? AND item_name = ?
            """,
            (remaining, chat_id, item_name),
        )
    else:
        connection.execute(
            """
            DELETE FROM inventory
            WHERE chat_id = ? AND item_name = ?
            """,
            (chat_id, item_name),
        )
    return remaining


def _record_support(
    connection: sqlite3.Connection,
    chat_id: int,
    round_number: int,
    actor_user_id: int,
    target_user_id: int,
    item_name: str,
    restored: int,
) -> None:
    connection.execute(
        """
        INSERT INTO party_support_history(
            chat_id,
            round_number,
            actor_user_id,
            target_user_id,
            item_name,
            restored_hp,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chat_id,
            round_number,
            actor_user_id,
            target_user_id,
            item_name,
            restored,
            datetime.now(UTC).isoformat(timespec="seconds"),
        ),
    )


def _denied(
    reason: str,
    state: dict[str, Any] | None = None,
) -> SupportActionResult:
    return SupportActionResult(
        False,
        reason,
        state,
        None,
        None,
        None,
        0,
        0,
        0,
        (),
        False,
        False,
        False,
    )


def _heal(
    path: Path,
    chat_id: int,
    actor_user_id: int,
    target_user_id: int,
    item_code: str,
) -> SupportActionResult:
    item_name = HEALING_ITEMS_BY_CODE.get(item_code)
    if item_name is None:
        return _denied("Неизвестное лечебное средство.")

    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        state = _load_state(connection, chat_id)
        if (
            not state
            or not bool(state.get("party_mode", False))
            or not living_enemies(state)
        ):
            connection.rollback()
            return _denied("Партийный бой не найден.", state)

        reason = action_guard(state, actor_user_id)
        if reason:
            connection.rollback()
            return _denied(reason, state)

        actor = party_member(state, actor_user_id)
        target = party_member(state, target_user_id)
        if actor is None or target is None:
            connection.rollback()
            return _denied("Участник партии не найден.", state)

        character = target["character"]
        current_hp = int(character.get("current_hp", 0))
        max_hp = int(character.get("max_hp", 1))
        if current_hp >= max_hp:
            connection.rollback()
            return _denied("У этого героя уже полное здоровье.", state)

        remaining = _consume_item(connection, chat_id, item_name)
        if remaining is None:
            connection.rollback()
            return _denied(f"В общем инвентаре нет предмета «{item_name}».", state)

        healing = use_healing_item(character, item_name)
        restored = int(healing["restored"])
        rolled = int(healing["rolled"])
        mark_acted(state, actor_user_id)
        original_round = int(state.get("round", 1))
        enemy_events: tuple[dict[str, Any], ...] = ()
        round_complete = False
        defeat = False
        shield_expired = False

        if round_ready(state):
            round_complete = True
            phase = resolve_party_enemy_phase(state)
            enemy_events = tuple(phase["events"])
            defeat = bool(phase["defeat"])
            shield_expired = bool(phase["shield_expired"])

        _write_party(connection, chat_id, state)
        if defeat:
            connection.execute(
                "DELETE FROM combats WHERE chat_id = ?",
                (chat_id,),
            )
        else:
            _write_state(connection, chat_id, state)
        _record_support(
            connection,
            chat_id,
            original_round,
            actor_user_id,
            target_user_id,
            item_name,
            restored,
        )
        connection.commit()

        return SupportActionResult(
            True,
            "",
            state,
            actor,
            target,
            item_name,
            rolled,
            restored,
            remaining,
            enemy_events,
            round_complete,
            defeat,
            shield_expired,
        )


class PartySupportStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def heal(
        self,
        chat_id: int,
        actor_user_id: int,
        target_user_id: int,
        item_code: str,
    ) -> SupportActionResult:
        return await asyncio.to_thread(
            _heal,
            self.path,
            chat_id,
            actor_user_id,
            target_user_id,
            item_code,
        )
