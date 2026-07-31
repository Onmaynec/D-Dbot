from __future__ import annotations

import random
import re
from dataclasses import dataclass

SUPPORTED_DICE = {4, 6, 8, 10, 12, 20, 100}
DICE_RE = re.compile(r"^(?:(?P<count>\d{1,2}))?d(?P<sides>\d{1,3})(?P<modifier>[+-]\d+)?$", re.I)


@dataclass(frozen=True, slots=True)
class RollResult:
    notation: str
    rolls: tuple[int, ...]
    modifier: int
    total: int


def roll_die(sides: int, rng: random.Random | None = None) -> int:
    if sides not in SUPPORTED_DICE:
        raise ValueError(f"Неподдерживаемый кубик d{sides}")
    roller = rng or random
    return roller.randint(1, sides)


def parse_and_roll(notation: str, rng: random.Random | None = None) -> RollResult:
    normalized = notation.strip().lower().replace(" ", "")
    match = DICE_RE.fullmatch(normalized)
    if not match:
        raise ValueError("Формат броска: d20, 2d6 или d20+3")

    count = int(match.group("count") or 1)
    sides = int(match.group("sides"))
    modifier = int(match.group("modifier") or 0)

    if count < 1 or count > 20:
        raise ValueError("Можно бросить от 1 до 20 кубиков за раз")
    if sides not in SUPPORTED_DICE:
        supported = ", ".join(f"d{value}" for value in sorted(SUPPORTED_DICE))
        raise ValueError(f"Доступные кубики: {supported}")

    roller = rng or random
    rolls = tuple(roller.randint(1, sides) for _ in range(count))
    total = sum(rolls) + modifier
    return RollResult(normalized, rolls, modifier, total)


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def format_modifier(value: int) -> str:
    return f"{value:+d}"
