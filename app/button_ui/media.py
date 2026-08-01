from __future__ import annotations

from pathlib import Path
from typing import Any

from aiogram.types import FSInputFile, Message

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets" / "images"
SCENE_FILES = {
    "start": "start.jpg", "campaign": "campaign.jpg", "character": "character.jpg",
    "quest": "quest.jpg", "npc": "npc.jpg", "encounter_friendly": "encounter_friendly.jpg",
    "encounter_neutral": "encounter_neutral.jpg", "encounter_hostile": "encounter_hostile.jpg",
    "combat": "combat.jpg", "attack": "attack.jpg", "spell": "spell.jpg", "rest": "rest.jpg",
    "levelup": "levelup.jpg", "loot_common": "loot_common.jpg", "loot_rare": "loot_rare.jpg",
    "journal": "journal.jpg",
}


def scene_path(scene: str) -> Path:
    return ASSETS_DIR / SCENE_FILES.get(scene, SCENE_FILES["start"])


def journal_thumbnail() -> FSInputFile:
    return FSInputFile(ASSETS_DIR / "journal_thumb.jpg")


def fit_caption(text: str, limit: int = 1024) -> str:
    return text if len(text) <= limit else text[: limit - 2].rstrip() + "…"


async def send_scene(message: Message, scene: str, caption: str, reply_markup: Any | None = None) -> None:
    path = scene_path(scene)
    if path.exists():
        await message.answer_photo(FSInputFile(path), caption=fit_caption(caption), reply_markup=reply_markup)
    else:
        await message.answer(fit_caption(caption), reply_markup=reply_markup)
