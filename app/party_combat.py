from __future__ import annotations

import asyncio
import copy
import json
import random
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.battle_rewards import BattleReward, ensure_battle_id, grant_battle_reward
from app.combat import attack, cast_spell, living_enemies
from app.dice import ability_modifier
from app.tactical_items import advance_shield, armor_bonus, trigger_phoenix


@dataclass(frozen=True, slots=True)
class PartyActionResult:
    allowed: bool
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


def prepare_party_state(
    state: dict[str, Any],
    members: list[dict[str, Any]],
) -> dict[str, Any]:
    roster = [
        {
            "user_id": int(member["user_id"]),
            "display_name": str(member["display_name"]),
            "character": copy.deepcopy(member["character"]),
        }
        for member in members
        if isinstance(member.get("character"), dict)
    ]
    if not roster:
        return state
    state["party_mode"] = True
    state["party"] = roster
    state["acted_user_ids"] = []
    ensure_battle_id(state)
    return state


def party_member(state: dict[str, Any], user_id: int) -> dict[str, Any] | None:
    return next(
        (
            member
            for member in state.get("party", [])
            if int(member.get("user_id", 0)) == int(user_id)
        ),
        None,
    )


def living_party(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        member
        for member in state.get("party", [])
        if int(member.get("character", {}).get("current_hp", 0)) > 0
    ]


def action_guard(state: dict[str, Any], user_id: int) -> str:
    actor = party_member(state, user_id)
    if actor is None:
        return "Сначала вступи в партию, чтобы действовать в этом бою."
    if int(actor["character"].get("current_hp", 0)) <= 0:
        return "Твой герой без сознания и не может действовать."
    if int(user_id) in {int(value) for value in state.get("acted_user_ids", [])}:
        return "Ты уже действовал в этом раунде."
    return ""


def mark_acted(state: dict[str, Any], user_id: int) -> None:
    acted = {int(value) for value in state.get("acted_user_ids", [])}
    acted.add(int(user_id))
    state["acted_user_ids"] = sorted(acted)


def round_ready(state: dict[str, Any]) -> bool:
    living_ids = {int(member["user_id"]) for member in living_party(state)}
    acted = {int(value) for value in state.get("acted_user_ids", [])}
    return bool(living_ids) and living_ids.issubset(acted)


def pending_members(state: dict[str, Any]) -> list[dict[str, Any]]:
    acted = {int(value) for value in state.get("acted_user_ids", [])}
    return [
        member
        for member in living_party(state)
        if int(member["user_id"]) not in acted
    ]


def resolve_party_enemy_phase(
    state: dict[str, Any],
    rng: random.Random | None = None,
) -> dict[str, Any]:
    roller = rng or random
    shield_bonus = armor_bonus(state)
    events: list[dict[str, Any]] = []

    for enemy in living_enemies(state):
        targets = living_party(state)
        if not targets:
            break
        target = roller.choice(targets)
        character = target["character"]
        dexterity = int(character["abilities"]["ЛОВ"])
        armor_class = 10 + ability_modifier(dexterity) + shield_bonus
        natural = roller.randint(1, 20)
        total = natural + int(enemy.get("attack_bonus", 2))
        critical = natural == 20
        hit = critical or (natural != 1 and total >= armor_class)
        damage = 0
        revived = False

        if hit:
            dice_count = 2 if critical else 1
            damage = sum(
                roller.randint(1, int(enemy.get("damage_die", 6)))
                for _ in range(dice_count)
            )
            damage += max(0, int(enemy.get("attack_bonus", 2)) - 2)
            damage = max(1, damage)
            character["current_hp"] = max(
                0,
                int(character["current_hp"]) - damage,
            )
            if int(character["current_hp"]) == 0:
                revived_hp = trigger_phoenix(state, int(character["max_hp"]))
                if revived_hp is not None:
                    character["current_hp"] = revived_hp
                    revived = True

        events.append(
            {
                "enemy": str(enemy["name"]),
                "target_user_id": int(target["user_id"]),
                "target_display_name": str(target["display_name"]),
                "target_name": str(character["name"]),
                "natural": natural,
                "total": total,
                "armor_class": armor_class,
                "critical": critical,
                "hit": hit,
                "damage": damage,
                "current_hp": int(character["current_hp"]),
                "max_hp": int(character["max_hp"]),
                "revived": revived,
            }
        )

    shield_expired = advance_shield(state) if shield_bonus else False
    state["round"] = int(state.get("round", 1)) + 1
    state["acted_user_ids"] = []
    return {
        "events": events,
        "defeat": not living_party(state),
        "shield_expired": shield_expired,
    }


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS party_combat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL CHECK(action_type IN ('attack', 'spell')),
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_party_combat_history_chat_id
        ON party_combat_history(chat_id, id DESC);
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


def _record_action(
    connection: sqlite3.Connection,
    chat_id: int,
    round_number: int,
    user_id: int,
    action_type: str,
    payload: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO party_combat_history(
            chat_id, round_number, actor_user_id, action_type, payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            chat_id,
            round_number,
            user_id,
            action_type,
            json.dumps(payload, ensure_ascii=False),
            datetime.now(UTC).isoformat(timespec="seconds"),
        ),
    )


def _finish_or_save(
    connection: sqlite3.Connection,
    chat_id: int,
    state: dict[str, Any],
    finished: bool,
) -> None:
    _write_party(connection, chat_id, state)
    if finished:
        connection.execute("DELETE FROM combats WHERE chat_id = ?", (chat_id,))
    else:
        _write_state(connection, chat_id, state)


def _denied(
    reason: str,
    state: dict[str, Any] | None = None,
) -> PartyActionResult:
    return PartyActionResult(
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


def _resolve_round(
    state: dict[str, Any],
    victory: bool,
) -> tuple[tuple[dict[str, Any], ...], bool, bool, bool]:
    enemy_events: tuple[dict[str, Any], ...] = ()
    round_complete = False
    defeat = False
    shield_expired = False
    if not victory and round_ready(state):
        round_complete = True
        phase = resolve_party_enemy_phase(state)
        enemy_events = tuple(phase["events"])
        defeat = bool(phase["defeat"])
        shield_expired = bool(phase["shield_expired"])
    return enemy_events, round_complete, defeat, shield_expired


def _reward_payload(reward: BattleReward | None) -> dict[str, Any] | None:
    if reward is None:
        return None
    return {
        "xp_each": reward.xp_each,
        "gold": reward.gold,
        "item_name": reward.item_name,
        "quantity": reward.quantity,
    }


def _attack(
    path: Path,
    chat_id: int,
    user_id: int,
    target_text: str,
) -> PartyActionResult:
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        state = _load_state(connection, chat_id)
        if not state or not bool(state.get("party_mode", False)):
            connection.rollback()
            return _denied("Партийный бой не найден.", state)

        reason = action_guard(state, user_id)
        if reason:
            connection.rollback()
            return _denied(reason, state)

        actor = party_member(state, user_id)
        assert actor is not None
        character = actor["character"]
        modifier = ability_modifier(int(character["abilities"]["СИЛ"]))
        level = int(character.get("level", 1))
        proficiency = 2 + max(0, (level - 1) // 4)
        try:
            result = attack(
                state,
                target_text,
                modifier + proficiency,
                modifier,
            )
        except ValueError as error:
            connection.rollback()
            return _denied(str(error), state)

        if result["defeated"]:
            character["xp"] = int(character.get("xp", 0)) + int(result["xp"])
        mark_acted(state, user_id)
        original_round = int(state.get("round", 1))
        victory = not living_enemies(state)
        enemy_events, round_complete, defeat, shield_expired = _resolve_round(
            state,
            victory,
        )
        reward = grant_battle_reward(connection, chat_id, state) if victory else None

        finished = victory or defeat
        _finish_or_save(connection, chat_id, state, finished)
        _record_action(
            connection,
            chat_id,
            original_round,
            user_id,
            "attack",
            {
                "target": result["target"]["name"],
                "roll": result["total"],
                "damage": result["damage"],
                "defeated": result["defeated"],
                "round_complete": round_complete,
                "enemy_events": enemy_events,
                "reward": _reward_payload(reward),
            },
        )
        connection.commit()
        return PartyActionResult(
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


def _spell(
    path: Path,
    chat_id: int,
    user_id: int,
    spell: dict[str, Any],
) -> PartyActionResult:
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        state = _load_state(connection, chat_id)
        if not state or not bool(state.get("party_mode", False)):
            connection.rollback()
            return _denied("Партийный бой не найден.", state)

        reason = action_guard(state, user_id)
        if reason:
            connection.rollback()
            return _denied(reason, state)

        actor = party_member(state, user_id)
        assert actor is not None
        character = actor["character"]
        level = int(character.get("level", 1))
        modifier = (
            ability_modifier(int(character["abilities"]["МДР"]))
            + 2
            + max(0, (level - 1) // 4)
        )
        try:
            result = cast_spell(state, spell, modifier)
        except ValueError as error:
            connection.rollback()
            return _denied(str(error), state)

        if result["defeated"]:
            character["xp"] = int(character.get("xp", 0)) + int(result["xp"])
        mark_acted(state, user_id)
        original_round = int(state.get("round", 1))
        victory = not living_enemies(state)
        enemy_events, round_complete, defeat, shield_expired = _resolve_round(
            state,
            victory,
        )
        reward = grant_battle_reward(connection, chat_id, state) if victory else None

        finished = victory or defeat
        _finish_or_save(connection, chat_id, state, finished)
        _record_action(
            connection,
            chat_id,
            original_round,
            user_id,
            "spell",
            {
                "spell": spell["name"],
                "target": result["target"]["name"],
                "roll": result["total"],
                "damage": result["damage"],
                "defeated": result["defeated"],
                "round_complete": round_complete,
                "enemy_events": enemy_events,
                "reward": _reward_payload(reward),
            },
        )
        connection.commit()
        return PartyActionResult(
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


def _start(
    path: Path,
    chat_id: int,
    state: dict[str, Any],
    members: list[dict[str, Any]],
) -> dict[str, Any]:
    prepared = prepare_party_state(state, members)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        _write_state(connection, chat_id, prepared)
        connection.commit()
    return prepared


class PartyCombatStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def start(
        self,
        chat_id: int,
        state: dict[str, Any],
        members: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            _start,
            self.path,
            chat_id,
            state,
            members,
        )

    async def attack(
        self,
        chat_id: int,
        user_id: int,
        target_text: str,
    ) -> PartyActionResult:
        return await asyncio.to_thread(
            _attack,
            self.path,
            chat_id,
            user_id,
            target_text,
        )

    async def spell(
        self,
        chat_id: int,
        user_id: int,
        spell: dict[str, Any],
    ) -> PartyActionResult:
        return await asyncio.to_thread(
            _spell,
            self.path,
            chat_id,
            user_id,
            spell,
        )
