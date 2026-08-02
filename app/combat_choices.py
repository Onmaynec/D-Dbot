from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.battle_rewards import BattleReward, grant_battle_reward
from app.combat import attack, living_enemies
from app.dice import ability_modifier
from app.equipment import equipment_bonuses
from app.party_combat import (
    _finish_or_save,
    _load_state,
    _resolve_round,
    action_guard,
    mark_acted,
    party_member,
)


@dataclass(frozen=True, slots=True)
class CombatChoiceResult:
    ok: bool
    reason: str
    state: dict[str, Any] | None
    actor: dict[str, Any] | None
    action: dict[str, Any] | None
    enemy_events: tuple[dict[str, Any], ...]
    round_complete: bool
    victory: bool
    defeat: bool
    shield_expired: bool
    reward: BattleReward | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS combat_choice_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL CHECK(action_type IN ('guard', 'power_attack')),
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_combat_choice_history_chat
        ON combat_choice_history(chat_id, id DESC);
        """
    )


def _record(
    connection: sqlite3.Connection,
    chat_id: int,
    round_number: int,
    user_id: int,
    action_type: str,
    payload: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO combat_choice_history(
            chat_id, round_number, actor_user_id, action_type, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            chat_id,
            round_number,
            user_id,
            action_type,
            json.dumps(payload, ensure_ascii=False),
            _now(),
        ),
    )


def _denied(reason: str, state: dict[str, Any] | None = None) -> CombatChoiceResult:
    return CombatChoiceResult(
        False,
        reason,
        state,
        None,
        None,
        (),
        False,
        False,
        False,
        False,
        None,
    )


def _guard(path: Path, chat_id: int, user_id: int) -> CombatChoiceResult:
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        state = _load_state(connection, chat_id)
        if not state or not bool(state.get("party_mode", False)) or not living_enemies(state):
            connection.rollback()
            return _denied("Активный партийный бой не найден.", state)
        reason = action_guard(state, user_id)
        if reason:
            connection.rollback()
            return _denied(reason, state)
        actor = party_member(state, user_id)
        assert actor is not None
        bonuses = equipment_bonuses(actor["character"])
        guard_ac = 3 + bonuses["guard"]
        guarded = {int(value) for value in state.get("guard_user_ids", [])}
        guarded.add(int(user_id))
        state["guard_user_ids"] = sorted(guarded)
        mark_acted(state, user_id)
        original_round = int(state.get("round", 1))
        enemy_events, round_complete, defeat, shield_expired = _resolve_round(state, False)
        _finish_or_save(connection, chat_id, state, defeat)
        action = {"kind": "guard", "armor_bonus": guard_ac}
        _record(
            connection,
            chat_id,
            original_round,
            user_id,
            "guard",
            {
                "armor_bonus": guard_ac,
                "round_complete": round_complete,
                "enemy_events": enemy_events,
            },
        )
        connection.commit()
        return CombatChoiceResult(
            True,
            "",
            state,
            actor,
            action,
            enemy_events,
            round_complete,
            False,
            defeat,
            shield_expired,
            None,
        )


def _power_attack(
    path: Path,
    chat_id: int,
    user_id: int,
    target_text: str,
) -> CombatChoiceResult:
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        state = _load_state(connection, chat_id)
        if not state or not bool(state.get("party_mode", False)) or not living_enemies(state):
            connection.rollback()
            return _denied("Активный партийный бой не найден.", state)
        reason = action_guard(state, user_id)
        if reason:
            connection.rollback()
            return _denied(reason, state)
        actor = party_member(state, user_id)
        assert actor is not None
        character = actor["character"]
        strength = ability_modifier(int(character["abilities"]["СИЛ"]))
        level = int(character.get("level", 1))
        proficiency = 2 + max(0, (level - 1) // 4)
        equipment = equipment_bonuses(character)
        try:
            result = attack(
                state,
                target_text,
                strength + proficiency - 2,
                strength + equipment["damage"] + 4,
            )
        except ValueError as error:
            connection.rollback()
            return _denied(str(error), state)
        result["style"] = "power_attack"
        result["attack_penalty"] = -2
        result["style_damage_bonus"] = 4
        result["equipment_damage_bonus"] = equipment["damage"]
        if result["defeated"]:
            character["xp"] = int(character.get("xp", 0)) + int(result["xp"])
        mark_acted(state, user_id)
        original_round = int(state.get("round", 1))
        victory = not living_enemies(state)
        enemy_events, round_complete, defeat, shield_expired = _resolve_round(state, victory)
        reward = grant_battle_reward(connection, chat_id, state) if victory else None
        _finish_or_save(connection, chat_id, state, victory or defeat)
        _record(
            connection,
            chat_id,
            original_round,
            user_id,
            "power_attack",
            {
                "target": result["target"]["name"],
                "roll": result["total"],
                "damage": result["damage"],
                "defeated": result["defeated"],
                "equipment_damage_bonus": equipment["damage"],
                "round_complete": round_complete,
                "reward": (
                    {
                        "xp_each": reward.xp_each,
                        "gold": reward.gold,
                        "item_name": reward.item_name,
                    }
                    if reward
                    else None
                ),
            },
        )
        connection.commit()
        return CombatChoiceResult(
            True,
            "",
            state,
            actor,
            result,
            enemy_events,
            round_complete,
            victory,
            defeat,
            shield_expired,
            reward,
        )


class CombatChoiceStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def guard(self, chat_id: int, user_id: int) -> CombatChoiceResult:
        return await asyncio.to_thread(_guard, self.path, chat_id, user_id)

    async def power_attack(
        self,
        chat_id: int,
        user_id: int,
        target_text: str,
    ) -> CombatChoiceResult:
        return await asyncio.to_thread(
            _power_attack,
            self.path,
            chat_id,
            user_id,
            target_text,
        )
