from __future__ import annotations

import base64
import html
import re
from pathlib import Path
from typing import Any

from aiogram.types import FSInputFile, Message

from app.button_ui.image_data_0 import IMAGE_DATA_0
from app.button_ui.image_data_1 import IMAGE_DATA_1
from app.button_ui.image_data_2 import IMAGE_DATA_2
from app.button_ui.image_data_3 import IMAGE_DATA_3
from app.button_ui.image_data_4 import IMAGE_DATA_4

ASSETS_DIR = Path(__file__).resolve().parents[2] / "data" / "button_ui_images"
IMAGE_DATA: dict[str, str] = {}
for image_group in (IMAGE_DATA_0, IMAGE_DATA_1, IMAGE_DATA_2, IMAGE_DATA_3, IMAGE_DATA_4):
    IMAGE_DATA.update(image_group)

SCENE_FILES = {
    "start": "start.jpg", "campaign": "campaign.jpg", "character": "character.jpg",
    "quest": "quest.jpg", "npc": "npc.jpg", "encounter_friendly": "encounter_friendly.jpg",
    "encounter_neutral": "encounter_neutral.jpg", "encounter_hostile": "encounter_hostile.jpg",
    "combat": "combat.jpg", "attack": "attack.jpg", "spell": "spell.jpg", "rest": "rest.jpg",
    "levelup": "levelup.jpg", "loot_common": "loot_common.jpg", "loot_rare": "loot_rare.jpg",
    "journal": "journal.jpg",
}


def ensure_assets() -> None:
    """Распаковывает встроенные иллюстрации при первом запуске бота."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, encoded in IMAGE_DATA.items():
        path = ASSETS_DIR / filename
        if not path.exists() or path.stat().st_size == 0:
            path.write_bytes(base64.b64decode(encoded))


def scene_path(scene: str) -> Path:
    ensure_assets()
    return ASSETS_DIR / SCENE_FILES.get(scene, SCENE_FILES["start"])


def journal_thumbnail() -> FSInputFile:
    ensure_assets()
    return FSInputFile(ASSETS_DIR / "journal_thumb.jpg")


def _plain_text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value))


def _split_plain_caption(value: str, limit: int = 1024) -> list[str]:
    text = _plain_text(value).strip()
    if not text:
        return ["🖼️ Сцена приключения"]
    chunks: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        chunks.append(text)
    return chunks


async def send_scene(message: Message, scene: str, caption: str, reply_markup: Any | None = None) -> None:
    path = scene_path(scene)
    if len(caption) <= 1024:
        await message.answer_photo(FSInputFile(path), caption=caption, reply_markup=reply_markup)
        return

    # Telegram ограничивает подпись к фотографии 1024 символами. Для длинного журнала
    # повторяем иллюстрацию, чтобы каждое отправленное ботом игровое сообщение оставалось визуальным.
    chunks = _split_plain_caption(caption)
    for index, chunk in enumerate(chunks):
        markup = reply_markup if index == len(chunks) - 1 else None
        await message.answer_photo(FSInputFile(path), caption=chunk, reply_markup=markup)
