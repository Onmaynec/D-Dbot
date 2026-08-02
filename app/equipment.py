from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class EquipmentItem:
    code: str
    name: str
    slot: str
    rarity: str
    price: int
    damage_bonus: int = 0
    armor_bonus: int = 0
    spell_damage_bonus: int = 0
    guard_bonus: int = 0
    description: str = ""


EQUIPMENT: tuple[EquipmentItem, ...] = (
    EquipmentItem(
        "iron_sword",
        "Железный меч",
        "weapon",
        "обычная",
        70,
        damage_bonus=1,
        description="Надёжное оружие: +1 к физическому урону.",
    ),
    EquipmentItem(
        "hunter_bow",
        "Лук следопыта",
        "weapon",
        "редкая",
        130,
        damage_bonus=2,
        description="Точный дальний бой: +2 к физическому урону.",
    ),
    EquipmentItem(
        "war_axe",
        "Секира налётчика",
        "weapon",
        "редкая",
        175,
        damage_bonus=3,
        description="Тяжёлый удар: +3 к физическому урону.",
    ),
    EquipmentItem(
        "void_blade",
        "Клинок Бездны",
        "weapon",
        "эпическая",
        360,
        damage_bonus=5,
        description="Оружие поздней игры: +5 к физическому урону.",
    ),
    EquipmentItem(
        "leather_armor",
        "Кожаный доспех",
        "armor",
        "обычная",
        80,
        armor_bonus=1,
        description="Лёгкая защита: +1 КД.",
    ),
    EquipmentItem(
        "chainmail",
        "Кольчуга стража",
        "armor",
        "редкая",
        170,
        armor_bonus=2,
        description="Надёжная броня: +2 КД.",
    ),
    EquipmentItem(
        "dragon_plate",
        "Драконья кираса",
        "armor",
        "эпическая",
        390,
        armor_bonus=3,
        guard_bonus=1,
        description="+3 КД и усиленная защитная стойка.",
    ),
    EquipmentItem(
        "apprentice_staff",
        "Посох ученика",
        "weapon",
        "обычная",
        90,
        spell_damage_bonus=1,
        description="+1 к урону заклинаний.",
    ),
    EquipmentItem(
        "astral_staff",
        "Астральный посох",
        "weapon",
        "эпическая",
        340,
        spell_damage_bonus=4,
        description="+4 к урону заклинаний.",
    ),
    EquipmentItem(
        "lucky_charm",
        "Талисман удачи",
        "trinket",
        "редкая",
        145,
        damage_bonus=1,
        spell_damage_bonus=1,
        description="+1 к физическому и магическому урону.",
    ),
    EquipmentItem(
        "guardian_signet",
        "Перстень хранителя",
        "trinket",
        "редкая",
        190,
        armor_bonus=1,
        guard_bonus=2,
        description="+1 КД и +2 КД в защитной стойке.",
    ),
    EquipmentItem(
        "phoenix_medallion",
        "Медальон феникса",
        "trinket",
        "эпическая",
        420,
        armor_bonus=1,
        damage_bonus=2,
        spell_damage_bonus=2,
        description="Сбалансированная реликвия героя высокого уровня.",
    ),
)

EQUIPMENT_BY_CODE = {item.code: item for item in EQUIPMENT}
SLOT_NAMES = {"weapon": "Оружие", "armor": "Доспех", "trinket": "Талисман"}


@dataclass(frozen=True, slots=True)
class EquipmentActionResult:
    ok: bool
    reason: str
    balance: int
    item: EquipmentItem | None = None
    character: dict[str, Any] | None = None


def equipment_bonuses(character: dict[str, Any]) -> dict[str, int]:
    equipped = character.get("equipment", {})
    if not isinstance(equipped, dict):
        equipped = {}
    totals = {
        "damage": 0,
        "armor": 0,
        "spell_damage": 0,
        "guard": 0,
    }
    for code in equipped.values():
        item = EQUIPMENT_BY_CODE.get(str(code))
        if item is None:
            continue
        totals["damage"] += item.damage_bonus
        totals["armor"] += item.armor_bonus
        totals["spell_damage"] += item.spell_damage_bonus
        totals["guard"] += item.guard_bonus
    return totals


def equipped_item_names(character: dict[str, Any]) -> dict[str, str]:
    equipped = character.get("equipment", {})
    if not isinstance(equipped, dict):
        return {}
    result: dict[str, str] = {}
    for slot, code in equipped.items():
        item = EQUIPMENT_BY_CODE.get(str(code))
        if item is not None:
            result[str(slot)] = item.name
    return result


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS owned_equipment (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            item_code TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity >= 0),
            acquired_at TEXT NOT NULL,
            PRIMARY KEY(chat_id, user_id, item_code)
        );

        CREATE TABLE IF NOT EXISTS equipment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('buy', 'equip', 'unequip')),
            item_code TEXT,
            slot TEXT,
            gold_delta INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_equipment_history_chat
        ON equipment_history(chat_id, id DESC);

        CREATE TABLE IF NOT EXISTS party_wallets (
            chat_id INTEGER PRIMARY KEY,
            gold INTEGER NOT NULL DEFAULT 100 CHECK(gold >= 0)
        );
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


def _load_member(
    connection: sqlite3.Connection,
    chat_id: int,
    user_id: int,
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT display_name, character_json FROM party_members "
        "WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return {"display_name": str(row[0]), "character": json.loads(row[1])}


def _save_member(
    connection: sqlite3.Connection,
    chat_id: int,
    user_id: int,
    member: dict[str, Any],
) -> None:
    connection.execute(
        "UPDATE party_members SET character_json = ? WHERE chat_id = ? AND user_id = ?",
        (json.dumps(member["character"], ensure_ascii=False), chat_id, user_id),
    )


def _has_active_combat(connection: sqlite3.Connection, chat_id: int) -> bool:
    try:
        row = connection.execute(
            "SELECT 1 FROM combats WHERE chat_id = ? LIMIT 1",
            (chat_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


def _record(
    connection: sqlite3.Connection,
    chat_id: int,
    user_id: int,
    action: str,
    item_code: str | None,
    slot: str | None,
    gold_delta: int = 0,
) -> None:
    connection.execute(
        """
        INSERT INTO equipment_history(
            chat_id, user_id, action, item_code, slot, gold_delta, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (chat_id, user_id, action, item_code, slot, gold_delta, _now()),
    )


def _buy(path: Path, chat_id: int, user_id: int, item_code: str) -> EquipmentActionResult:
    item = EQUIPMENT_BY_CODE.get(item_code)
    if item is None:
        return EquipmentActionResult(False, "Предмет не найден.", 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        member = _load_member(connection, chat_id, user_id)
        balance = _wallet(connection, chat_id)
        if member is None:
            connection.rollback()
            return EquipmentActionResult(
                False,
                "Сначала вступи в партию — снаряжение закрепляется за твоим героем.",
                balance,
            )
        if balance < item.price:
            connection.rollback()
            return EquipmentActionResult(
                False,
                f"Не хватает золота: нужно {item.price}, в казне {balance}.",
                balance,
                item,
                member["character"],
            )
        connection.execute(
            "UPDATE party_wallets SET gold = gold - ? WHERE chat_id = ?",
            (item.price, chat_id),
        )
        connection.execute(
            """
            INSERT INTO owned_equipment(chat_id, user_id, item_code, quantity, acquired_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(chat_id, user_id, item_code) DO UPDATE SET
                quantity=owned_equipment.quantity + 1
            """,
            (chat_id, user_id, item.code, _now()),
        )
        _record(connection, chat_id, user_id, "buy", item.code, item.slot, -item.price)
        connection.commit()
        return EquipmentActionResult(
            True,
            "Покупка завершена.",
            balance - item.price,
            item,
            member["character"],
        )


def _equip(path: Path, chat_id: int, user_id: int, item_code: str) -> EquipmentActionResult:
    item = EQUIPMENT_BY_CODE.get(item_code)
    if item is None:
        return EquipmentActionResult(False, "Предмет не найден.", 0)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        balance = _wallet(connection, chat_id)
        if _has_active_combat(connection, chat_id):
            connection.rollback()
            return EquipmentActionResult(
                False,
                "Нельзя переодеваться во время активного боя.",
                balance,
                item,
            )
        member = _load_member(connection, chat_id, user_id)
        if member is None:
            connection.rollback()
            return EquipmentActionResult(False, "Сначала вступи в партию.", balance, item)
        owned = connection.execute(
            "SELECT quantity FROM owned_equipment "
            "WHERE chat_id = ? AND user_id = ? AND item_code = ?",
            (chat_id, user_id, item.code),
        ).fetchone()
        if owned is None or int(owned[0]) <= 0:
            connection.rollback()
            return EquipmentActionResult(
                False,
                "Сначала купи или получи этот предмет.",
                balance,
                item,
                member["character"],
            )
        character = member["character"]
        equipment = character.setdefault("equipment", {})
        if not isinstance(equipment, dict):
            equipment = {}
            character["equipment"] = equipment
        equipment[item.slot] = item.code
        _save_member(connection, chat_id, user_id, member)
        _record(connection, chat_id, user_id, "equip", item.code, item.slot)
        connection.commit()
        return EquipmentActionResult(True, "Предмет экипирован.", balance, item, character)


def _unequip(path: Path, chat_id: int, user_id: int, slot: str) -> EquipmentActionResult:
    if slot not in SLOT_NAMES:
        return EquipmentActionResult(False, "Неизвестный слот.", 0)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        balance = _wallet(connection, chat_id)
        if _has_active_combat(connection, chat_id):
            connection.rollback()
            return EquipmentActionResult(False, "Нельзя менять экипировку в бою.", balance)
        member = _load_member(connection, chat_id, user_id)
        if member is None:
            connection.rollback()
            return EquipmentActionResult(False, "Сначала вступи в партию.", balance)
        character = member["character"]
        equipment = character.get("equipment", {})
        if not isinstance(equipment, dict) or slot not in equipment:
            connection.rollback()
            return EquipmentActionResult(False, "Этот слот уже пуст.", balance, character=character)
        item_code = str(equipment.pop(slot))
        item = EQUIPMENT_BY_CODE.get(item_code)
        _save_member(connection, chat_id, user_id, member)
        _record(connection, chat_id, user_id, "unequip", item_code, slot)
        connection.commit()
        return EquipmentActionResult(True, "Предмет снят.", balance, item, character)


def _snapshot(path: Path, chat_id: int, user_id: int) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        balance = _wallet(connection, chat_id)
        member = _load_member(connection, chat_id, user_id)
        rows = connection.execute(
            """
            SELECT item_code, quantity
            FROM owned_equipment
            WHERE chat_id = ? AND user_id = ? AND quantity > 0
            ORDER BY item_code
            """,
            (chat_id, user_id),
        ).fetchall()
        connection.commit()
    owned = []
    for code, quantity in rows:
        item = EQUIPMENT_BY_CODE.get(str(code))
        if item is not None:
            owned.append({**asdict(item), "quantity": int(quantity)})
    character = member["character"] if member else None
    return {
        "balance": balance,
        "character": character,
        "owned": owned,
        "bonuses": equipment_bonuses(character or {}),
        "equipped": equipped_item_names(character or {}),
    }


class EquipmentStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def snapshot(self, chat_id: int, user_id: int) -> dict[str, Any]:
        return await asyncio.to_thread(_snapshot, self.path, chat_id, user_id)

    async def buy(self, chat_id: int, user_id: int, item_code: str) -> EquipmentActionResult:
        return await asyncio.to_thread(_buy, self.path, chat_id, user_id, item_code)

    async def equip(self, chat_id: int, user_id: int, item_code: str) -> EquipmentActionResult:
        return await asyncio.to_thread(_equip, self.path, chat_id, user_id, item_code)

    async def unequip(self, chat_id: int, user_id: int, slot: str) -> EquipmentActionResult:
        return await asyncio.to_thread(_unequip, self.path, chat_id, user_id, slot)
