from __future__ import annotations

import random
from typing import Any

DIFFICULTY_PRESETS: dict[str, dict[str, Any]] = {
    "easy": {
        "label": "лёгкая",
        "rooms": 4,
        "enemy_scale": 0.85,
        "trap_scale": 0.75,
        "reward_scale": 0.9,
    },
    "normal": {
        "label": "обычная",
        "rooms": 5,
        "enemy_scale": 1.0,
        "trap_scale": 1.0,
        "reward_scale": 1.0,
    },
    "hard": {
        "label": "хардкор",
        "rooms": 6,
        "enemy_scale": 1.3,
        "trap_scale": 1.35,
        "reward_scale": 1.35,
    },
}

DUNGEON_PREFIXES = [
    "Катакомбы", "Цитадель", "Лабиринт", "Гробница", "Шахты", "Обсерватория", "Храм",
]
DUNGEON_SUFFIXES = [
    "Пепельной Короны", "Безмолвного Колокола", "Алой Луны", "Забытого Короля",
    "Стеклянной Бездны", "Последнего Оракула", "Чёрного Солнца",
]
ROOM_TITLES = {
    "lore": ["Зал забытых фресок", "Архив без имён", "Галерея окаменевших масок"],
    "trap": ["Коридор лезвий", "Комната ложного пола", "Зал ядовитого тумана"],
    "treasure": ["Сломанная сокровищница", "Тайник картографа", "Кладовая древней стражи"],
    "shrine": ["Алтарь тихого света", "Источник серебряной воды", "Часовня последней надежды"],
    "encounter": ["Развилка со свежими следами", "Зал сторожевых статуй", "Подземный мост"],
}
ROOM_DESCRIPTIONS = {
    "lore": [
        "На стенах проступает хроника падения хозяев подземелья. Одна из сцен явно изображает вашу партию.",
        "В пыли лежат страницы дневника, написанные чернилами, которые всё ещё движутся по бумаге.",
        "Каменные маски шепчут разные версии одной и той же катастрофы.",
    ],
    "trap": [
        "Плиты под ногами проседают, и из стен вырываются ржавые клинки.",
        "Руны на полу вспыхивают, выпуская волну ледяного воздуха.",
        "Из трещин поднимается тяжёлый зелёный туман, обжигающий лёгкие.",
    ],
    "treasure": [
        "За обвалившейся кладкой обнаруживается сундук с уцелевшей печатью.",
        "В нише спрятан дорожный запас прежней экспедиции.",
        "Под статуей звенят монеты и лежит предмет, не тронутый временем.",
    ],
    "shrine": [
        "Тёплый свет алтаря затягивает раны и возвращает ясность мыслям.",
        "Вода из каменной чаши пахнет грозой и восстанавливает силы.",
        "Когда герой касается символа, подземелье на мгновение перестаёт дышать.",
    ],
    "encounter": [
        "В темноте слышатся осторожные шаги. Кто-то наблюдает, но пока не атакует.",
        "Древние статуи поворачивают головы вслед за каждым движением героев.",
        "На мосту лежит оружие недавней экспедиции, а внизу шевелится тьма.",
    ],
}
BOSSES = [
    {
        "name": "Смотритель Пепельных Врат",
        "description": "закованный в почерневшие латы страж, внутри которых горит холодное пламя",
        "base_hp": 42,
        "ac": 15,
        "attack_bonus": 5,
        "damage_die": 8,
        "xp": 220,
        "loot": "Печать Пепельных Врат",
    },
    {
        "name": "Матрона Стеклянного Роя",
        "description": "огромное существо из хрустальных пластин и множества зеркальных глаз",
        "base_hp": 48,
        "ac": 14,
        "attack_bonus": 6,
        "damage_die": 10,
        "xp": 260,
        "loot": "Осколок Сердца Роя",
    },
    {
        "name": "Безымянный Король Подземья",
        "description": "высокая тень в сломанной короне, управляющая цепями древних узников",
        "base_hp": 55,
        "ac": 16,
        "attack_bonus": 6,
        "damage_die": 10,
        "xp": 300,
        "loot": "Корона Безымянного Короля",
    },
]


def normalize_difficulty(value: str | None) -> str:
    return value if value in DIFFICULTY_PRESETS else "normal"


def difficulty_label(value: str | None) -> str:
    return str(DIFFICULTY_PRESETS[normalize_difficulty(value)]["label"])


def create_dungeon(
    party_level: int,
    difficulty: str = "normal",
    rng: random.Random | None = None,
) -> dict[str, Any]:
    roller = rng or random
    key = normalize_difficulty(difficulty)
    preset = DIFFICULTY_PRESETS[key]
    return {
        "name": f"{roller.choice(DUNGEON_PREFIXES)} {roller.choice(DUNGEON_SUFFIXES)}",
        "difficulty": key,
        "party_level": max(1, int(party_level)),
        "depth": 0,
        "max_depth": int(preset["rooms"]),
        "status": "active",
        "rooms": [],
        "gold_earned": 0,
        "boss": None,
    }


def _generate_boss(state: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    template = dict(rng.choice(BOSSES))
    level = max(1, int(state.get("party_level", 1)))
    preset = DIFFICULTY_PRESETS[normalize_difficulty(str(state.get("difficulty")))]
    scale = float(preset["enemy_scale"])
    max_hp = max(12, round((int(template["base_hp"]) + (level - 1) * 7) * scale))
    return {
        "name": template["name"],
        "description": template["description"],
        "hp": max_hp,
        "max_hp": max_hp,
        "ac": max(10, round(int(template["ac"]) + (level - 1) * 0.35)),
        "attack_bonus": max(1, round(int(template["attack_bonus"]) + (level - 1) * 0.45)),
        "damage_die": int(template["damage_die"]),
        "xp": int(template["xp"]) + (level - 1) * 35,
        "loot": template["loot"],
        "alive": True,
    }


def explore_next_room(state: dict[str, Any], rng: random.Random | None = None) -> dict[str, Any]:
    if state.get("status") != "active":
        raise ValueError("Экспедиция уже завершена")
    depth = int(state.get("depth", 0))
    maximum = int(state.get("max_depth", 1))
    if depth >= maximum:
        raise ValueError("Все комнаты уже исследованы")

    roller = rng or random
    depth += 1
    state["depth"] = depth
    difficulty = normalize_difficulty(str(state.get("difficulty")))
    preset = DIFFICULTY_PRESETS[difficulty]
    level = max(1, int(state.get("party_level", 1)))

    if depth == maximum:
        boss = _generate_boss(state, roller)
        state["boss"] = boss
        room = {
            "type": "boss",
            "title": "Тронный зал",
            "description": f"Путь преграждает {boss['name']} — {boss['description']}.",
            "depth": depth,
            "gold": 0,
            "damage": 0,
            "healing": 0,
            "loot": None,
        }
    else:
        room_type = roller.choices(
            ["lore", "trap", "treasure", "shrine", "encounter"],
            weights=[18, 20, 24, 16, 22],
            k=1,
        )[0]
        gold = 0
        damage = 0
        healing = 0
        loot: str | None = None
        if room_type == "trap":
            damage = max(1, round(roller.randint(2, 6) * level * float(preset["trap_scale"]) / 2))
        elif room_type == "treasure":
            gold = max(5, round(roller.randint(12, 28) * float(preset["reward_scale"])))
            loot = roller.choice(["Древний ключ", "Руна защиты", "Карта скрытого прохода", "Эликсир ясности"])
        elif room_type == "shrine":
            healing = max(2, roller.randint(4, 10) + level)
        elif room_type == "encounter":
            gold = max(0, round(roller.randint(0, 8) * float(preset["reward_scale"])))

        room = {
            "type": room_type,
            "title": roller.choice(ROOM_TITLES[room_type]),
            "description": roller.choice(ROOM_DESCRIPTIONS[room_type]),
            "depth": depth,
            "gold": gold,
            "damage": damage,
            "healing": healing,
            "loot": loot,
        }
        state["gold_earned"] = int(state.get("gold_earned", 0)) + gold

    state.setdefault("rooms", []).append(room)
    return room


def player_attack_boss(
    state: dict[str, Any],
    attack_modifier: int,
    damage_modifier: int,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    boss = state.get("boss")
    if not boss or not boss.get("alive", True) or int(boss.get("hp", 0)) <= 0:
        raise ValueError("В подземелье нет живого босса")
    roller = rng or random
    natural = roller.randint(1, 20)
    total = natural + int(attack_modifier)
    critical = natural == 20
    hit = critical or (natural != 1 and total >= int(boss["ac"]))
    damage = 0
    if hit:
        dice_count = 2 if critical else 1
        damage = max(1, sum(roller.randint(1, 8) for _ in range(dice_count)) + int(damage_modifier))
        boss["hp"] = max(0, int(boss["hp"]) - damage)
        if boss["hp"] == 0:
            boss["alive"] = False
    return {
        "natural": natural,
        "total": total,
        "critical": critical,
        "hit": hit,
        "damage": damage,
        "defeated": not boss.get("alive", True),
        "boss": boss,
    }


def boss_retaliation(
    state: dict[str, Any],
    player_ac: int,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    boss = state.get("boss")
    if not boss or not boss.get("alive", True):
        return {"natural": 0, "total": 0, "critical": False, "hit": False, "damage": 0}
    roller = rng or random
    natural = roller.randint(1, 20)
    total = natural + int(boss["attack_bonus"])
    critical = natural == 20
    hit = critical or (natural != 1 and total >= int(player_ac))
    damage = 0
    if hit:
        dice_count = 2 if critical else 1
        damage = max(1, sum(roller.randint(1, int(boss["damage_die"])) for _ in range(dice_count)))
    return {
        "natural": natural,
        "total": total,
        "critical": critical,
        "hit": hit,
        "damage": damage,
    }


def victory_rewards(state: dict[str, Any]) -> dict[str, Any]:
    boss = state.get("boss") or {}
    preset = DIFFICULTY_PRESETS[normalize_difficulty(str(state.get("difficulty")))]
    level = max(1, int(state.get("party_level", 1)))
    gold = max(25, round((45 + level * 18) * float(preset["reward_scale"])))
    return {
        "gold": gold,
        "xp": int(boss.get("xp", 0)),
        "loot": str(boss.get("loot", "Реликвия подземелья")),
    }
