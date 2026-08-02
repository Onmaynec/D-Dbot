from __future__ import annotations

import asyncio
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.dice import ability_modifier


@dataclass(frozen=True, slots=True)
class StoryOption:
    code: str
    title: str
    ability: str
    difficulty: int
    success_text: str
    failure_text: str
    success_gold: int = 0
    failure_gold: int = 0
    reward_item: str | None = None
    reward_rarity: str = "обычная"
    failure_damage: int = 0


@dataclass(frozen=True, slots=True)
class StoryScenario:
    code: str
    title: str
    scene: str
    description: str
    options: tuple[StoryOption, ...]


SCENARIOS: tuple[StoryScenario, ...] = (
    StoryScenario(
        "broken_bridge",
        "Мост над Бездной",
        "encounter_neutral",
        "Старый мост трещит над бездонным ущельем. На другой стороне виден запечатанный сундук.",
        (
            StoryOption(
                "leap",
                "🏃 Перепрыгнуть разлом",
                "ЛОВ",
                13,
                "Герои перелетают через разлом и добираются до сундука.",
                "Камень обрушивается, и партия едва выбирается обратно.",
                success_gold=45,
                reward_item="Серебряные стрелы",
                reward_rarity="редкая",
                failure_damage=3,
            ),
            StoryOption(
                "repair",
                "🪢 Укрепить мост",
                "ИНТ",
                11,
                "Расчёт оказывается верным: мост выдерживает всю партию.",
                "Неверно закреплённые тросы лопаются в самый неподходящий момент.",
                success_gold=25,
                failure_damage=1,
            ),
            StoryOption(
                "retreat",
                "🧭 Найти безопасный обход",
                "МДР",
                9,
                "Следопыт находит старую тропу. Награда меньше, но риска почти нет.",
                "Обход приводит к тупику и отнимает часть припасов.",
                success_gold=15,
                failure_gold=-8,
            ),
        ),
    ),
    StoryScenario(
        "masked_merchant",
        "Торговец без лица",
        "npc",
        "На перекрёстке стоит торговец в гладкой серебряной маске. Он предлагает карту, но явно что-то скрывает.",
        (
            StoryOption(
                "bargain",
                "🗣️ Сбить цену",
                "ХАР",
                12,
                "Торговец смеётся и уступает редкую вещь почти даром.",
                "Торговец замечает слабость и завышает цену.",
                success_gold=30,
                reward_item="Свиток удачи",
                reward_rarity="редкая",
                failure_gold=-15,
            ),
            StoryOption(
                "inspect",
                "🔍 Проверить товар",
                "ИНТ",
                13,
                "На карте обнаруживается тайный маршрут к сокровищам.",
                "Карта оказывается искусной подделкой.",
                success_gold=55,
                failure_gold=-10,
            ),
            StoryOption(
                "follow",
                "🕵️ Проследить за ним",
                "ЛОВ",
                14,
                "Партия находит тайник торговца.",
                "Слежка раскрыта, и наёмники устраивают засаду.",
                success_gold=70,
                failure_damage=4,
            ),
        ),
    ),
    StoryScenario(
        "cursed_shrine",
        "Проклятое святилище",
        "encounter_hostile",
        "Фиолетовое пламя горит без топлива. Руны обещают силу тому, кто выдержит испытание.",
        (
            StoryOption(
                "purify",
                "✨ Очистить руны",
                "МДР",
                14,
                "Свет вытесняет проклятие, оставляя благословенный трофей.",
                "Проклятие отвечает вспышкой боли.",
                success_gold=35,
                reward_item="Большое зелье лечения",
                reward_rarity="редкая",
                failure_damage=5,
            ),
            StoryOption(
                "study",
                "📖 Расшифровать письмена",
                "ИНТ",
                13,
                "Древняя формула раскрывает тайник жрецов.",
                "Неверно прочитанный символ активирует ловушку.",
                success_gold=60,
                failure_damage=3,
            ),
            StoryOption(
                "break",
                "🔨 Разрушить алтарь",
                "СИЛ",
                15,
                "Алтарь раскалывается, освобождая заключённую энергию.",
                "Камень не поддаётся, зато проклятие замечает героев.",
                success_gold=80,
                reward_item="Жетон судьбы",
                reward_rarity="эпическая",
                failure_damage=6,
            ),
        ),
    ),
    StoryScenario(
        "captured_scout",
        "Пленный разведчик",
        "encounter_friendly",
        "В придорожной клетке сидит разведчик враждебной фракции. Он утверждает, что знает слабое место ближайшей крепости.",
        (
            StoryOption(
                "free",
                "🗝️ Освободить и поверить",
                "ХАР",
                11,
                "Разведчик держит слово и приводит партию к складу припасов.",
                "Освобождённый пленник подаёт сигнал своим союзникам.",
                success_gold=40,
                reward_item="Зелье лечения",
                failure_damage=2,
            ),
            StoryOption(
                "interrogate",
                "⚖️ Провести допрос",
                "МДР",
                13,
                "Ложь быстро раскрывается, а полезные сведения остаются.",
                "Пленник запутывает следы и тянет время.",
                success_gold=55,
                failure_gold=-6,
            ),
            StoryOption(
                "pick_lock",
                "🧤 Незаметно снять замок",
                "ЛОВ",
                12,
                "Никто не замечает побега, а разведчик делится тайником.",
                "Стража слышит щелчок замка.",
                success_gold=50,
                failure_damage=3,
            ),
        ),
    ),
)

SCENARIO_BY_CODE = {scenario.code: scenario for scenario in SCENARIOS}


@dataclass(frozen=True, slots=True)
class StoryChoiceResult:
    ok: bool
    reason: str
    scenario: StoryScenario | None
    option: StoryOption | None
    natural: int
    modifier: int
    total: int
    success: bool
    gold_delta: int
    balance: int
    item_name: str | None
    damage_each: int


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS active_story_choices (
            chat_id INTEGER PRIMARY KEY,
            scenario_code TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS story_choice_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            scenario_code TEXT NOT NULL,
            option_code TEXT NOT NULL,
            natural INTEGER NOT NULL,
            modifier INTEGER NOT NULL,
            total INTEGER NOT NULL,
            success INTEGER NOT NULL,
            gold_delta INTEGER NOT NULL,
            item_name TEXT,
            damage_each INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_story_choice_history_chat
        ON story_choice_history(chat_id, id DESC);

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


def _party_characters(connection: sqlite3.Connection, chat_id: int) -> list[tuple[int, dict[str, Any]]]:
    rows = connection.execute(
        "SELECT user_id, character_json FROM party_members WHERE chat_id = ? ORDER BY user_id",
        (chat_id,),
    ).fetchall()
    return [(int(row[0]), json.loads(row[1])) for row in rows]


def _ability_modifier(characters: list[tuple[int, dict[str, Any]]], ability: str) -> int:
    values = [
        int(character.get("abilities", {}).get(ability, 10))
        for _, character in characters
    ]
    if not values:
        return 0
    average = round(sum(values) / len(values))
    return ability_modifier(average)


def _open(path: Path, chat_id: int) -> StoryScenario:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT scenario_code FROM active_story_choices WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if row is not None and str(row[0]) in SCENARIO_BY_CODE:
            connection.commit()
            return SCENARIO_BY_CODE[str(row[0])]
        recent = connection.execute(
            """
            SELECT scenario_code FROM story_choice_history
            WHERE chat_id = ? ORDER BY id DESC LIMIT 1
            """,
            (chat_id,),
        ).fetchone()
        choices = [scenario for scenario in SCENARIOS if recent is None or scenario.code != str(recent[0])]
        scenario = secrets.choice(choices or list(SCENARIOS))
        connection.execute(
            "INSERT OR REPLACE INTO active_story_choices(chat_id, scenario_code, created_at) VALUES (?, ?, ?)",
            (chat_id, scenario.code, _now()),
        )
        connection.commit()
        return scenario


def _resolve(
    path: Path,
    chat_id: int,
    user_id: int,
    option_code: str,
) -> StoryChoiceResult:
    with sqlite3.connect(path, timeout=10) as connection:
        _ensure_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            active_combat = connection.execute(
                "SELECT 1 FROM combats WHERE chat_id = ? LIMIT 1",
                (chat_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            active_combat = None
        if active_combat is not None:
            connection.rollback()
            return StoryChoiceResult(
                False,
                "Сначала заверши активный бой.",
                None,
                None,
                0,
                0,
                0,
                False,
                0,
                _wallet(connection, chat_id),
                None,
                0,
            )
        row = connection.execute(
            "SELECT scenario_code FROM active_story_choices WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if row is None:
            connection.rollback()
            return StoryChoiceResult(False, "Событие уже завершено.", None, None, 0, 0, 0, False, 0, 0, None, 0)
        scenario = SCENARIO_BY_CODE.get(str(row[0]))
        option = next((item for item in scenario.options if item.code == option_code), None) if scenario else None
        if scenario is None or option is None:
            connection.rollback()
            return StoryChoiceResult(False, "Вариант выбора устарел.", scenario, None, 0, 0, 0, False, 0, 0, None, 0)

        characters = _party_characters(connection, chat_id)
        if not characters:
            connection.rollback()
            return StoryChoiceResult(
                False,
                "Сначала собери партию.",
                scenario,
                option,
                0,
                0,
                0,
                False,
                0,
                _wallet(connection, chat_id),
                None,
                0,
            )

        natural = secrets.randbelow(20) + 1
        modifier = _ability_modifier(characters, option.ability)
        total = natural + modifier
        success = natural == 20 or (natural != 1 and total >= option.difficulty)
        gold_delta = option.success_gold if success else option.failure_gold
        damage_each = 0 if success else option.failure_damage
        item_name = option.reward_item if success else None
        balance = _wallet(connection, chat_id)
        applied_gold = max(-balance, gold_delta)
        balance_after = balance + applied_gold
        connection.execute(
            "UPDATE party_wallets SET gold = ? WHERE chat_id = ?",
            (balance_after, chat_id),
        )
        if item_name:
            connection.execute(
                """
                INSERT INTO inventory(chat_id, item_name, rarity, quantity)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(chat_id, item_name) DO UPDATE SET
                    quantity=inventory.quantity + 1,
                    rarity=excluded.rarity
                """,
                (chat_id, item_name, option.reward_rarity),
            )
        if damage_each:
            for member_user_id, character in characters:
                current = int(character.get("current_hp", 0))
                character["current_hp"] = max(1, current - damage_each) if current > 0 else 0
                connection.execute(
                    "UPDATE party_members SET character_json = ? WHERE chat_id = ? AND user_id = ?",
                    (json.dumps(character, ensure_ascii=False), chat_id, member_user_id),
                )
        connection.execute(
            """
            INSERT INTO story_choice_history(
                chat_id, user_id, scenario_code, option_code, natural, modifier, total,
                success, gold_delta, item_name, damage_each, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                scenario.code,
                option.code,
                natural,
                modifier,
                total,
                int(success),
                applied_gold,
                item_name,
                damage_each,
                _now(),
            ),
        )
        connection.execute("DELETE FROM active_story_choices WHERE chat_id = ?", (chat_id,))
        connection.commit()
        return StoryChoiceResult(
            True,
            "",
            scenario,
            option,
            natural,
            modifier,
            total,
            success,
            applied_gold,
            balance_after,
            item_name,
            damage_each,
        )


class StoryChoiceStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def open(self, chat_id: int) -> StoryScenario:
        return await asyncio.to_thread(_open, self.path, chat_id)

    async def resolve(self, chat_id: int, user_id: int, option_code: str) -> StoryChoiceResult:
        return await asyncio.to_thread(_resolve, self.path, chat_id, user_id, option_code)
