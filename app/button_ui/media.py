from __future__ import annotations

import base64
import html
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiogram.types import FSInputFile, Message

from app.button_ui.image_data_0 import IMAGE_DATA_0
from app.button_ui.image_data_1 import IMAGE_DATA_1
from app.button_ui.image_data_2 import IMAGE_DATA_2
from app.button_ui.image_data_3 import IMAGE_DATA_3
from app.button_ui.image_data_4 import IMAGE_DATA_4
from app.image_quality import upscale_image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ASSETS_DIR = PROJECT_ROOT / "assets" / "images_hq"
GENERATED_ASSETS_DIR = PROJECT_ROOT / "data" / "button_ui_images"
UPSCALED_ASSETS_DIR = PROJECT_ROOT / "data" / "button_ui_images_v4"

IMAGE_DATA: dict[str, str] = {}
for image_group in (IMAGE_DATA_0, IMAGE_DATA_1, IMAGE_DATA_2, IMAGE_DATA_3, IMAGE_DATA_4):
    IMAGE_DATA.update(image_group)

SCENE_FILES = {
    "start": "start.jpg",
    "campaign": "campaign.jpg",
    "character": "character.jpg",
    "quest": "quest.jpg",
    "npc": "npc.jpg",
    "encounter_friendly": "encounter_friendly.jpg",
    "encounter_neutral": "encounter_neutral.jpg",
    "encounter_hostile": "encounter_hostile.jpg",
    "combat": "combat.jpg",
    "attack": "attack.jpg",
    "spell": "spell.jpg",
    "rest": "rest.jpg",
    "levelup": "levelup.jpg",
    "loot_common": "loot_common.jpg",
    "loot_rare": "loot_rare.jpg",
    "journal": "journal.jpg",
}

ImageModeResolver = Callable[[int], Awaitable[str]]
_image_mode_resolver: ImageModeResolver | None = None


def configure_image_mode_resolver(resolver: ImageModeResolver | None) -> None:
    """Подключает сохранённый для чата режим отправки изображений."""
    global _image_mode_resolver
    _image_mode_resolver = resolver


def ensure_fallback_assets() -> None:
    """Распаковывает встроенные изображения предыдущих версий."""
    GENERATED_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, encoded in IMAGE_DATA.items():
        path = GENERATED_ASSETS_DIR / filename
        if not path.exists() or path.stat().st_size == 0:
            path.write_bytes(base64.b64decode(encoded))


def ensure_upscaled_assets() -> None:
    """Готовит улучшенные изображения один раз при первом запуске v4."""
    ensure_fallback_assets()
    UPSCALED_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for filename in set(SCENE_FILES.values()):
        destination = UPSCALED_ASSETS_DIR / filename
        if destination.exists() and destination.stat().st_size > 35_000:
            continue
        source = SOURCE_ASSETS_DIR / filename
        if not source.exists():
            source = GENERATED_ASSETS_DIR / filename
        if source.exists():
            try:
                upscale_image(source, destination)
            except Exception:
                # Бот продолжит работу со старым изображением даже при проблемах Pillow/файла.
                continue


def scene_path(scene: str) -> Path:
    filename = SCENE_FILES.get(scene, SCENE_FILES["start"])
    source_hq = SOURCE_ASSETS_DIR / filename
    if source_hq.exists() and source_hq.stat().st_size > 35_000:
        return source_hq

    ensure_upscaled_assets()
    upscaled = UPSCALED_ASSETS_DIR / filename
    if upscaled.exists() and upscaled.stat().st_size > 35_000:
        return upscaled

    ensure_fallback_assets()
    return GENERATED_ASSETS_DIR / filename


def journal_thumbnail() -> FSInputFile:
    return FSInputFile(scene_path("journal"), filename="journal.jpg")


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


async def _resolve_image_mode(chat_id: int) -> str:
    if _image_mode_resolver is None:
        return "photo"
    try:
        mode = await _image_mode_resolver(chat_id)
    except Exception:
        return "photo"
    return mode if mode in {"photo", "document"} else "photo"


async def send_scene(
    message: Message,
    scene: str,
    caption: str,
    reply_markup: Any | None = None,
) -> None:
    """Отправляет крупную сцену; document сохраняет файл без сжатия Telegram."""
    path = scene_path(scene)
    mode = await _resolve_image_mode(message.chat.id)

    if mode == "document":
        chunks = _split_plain_caption(caption, limit=1024)
        for index, chunk in enumerate(chunks):
            await message.answer_document(
                FSInputFile(path, filename=path.name),
                caption=chunk,
                reply_markup=reply_markup if index == len(chunks) - 1 else None,
            )
        return

    if len(caption) <= 1024:
        await message.answer_photo(
            FSInputFile(path, filename=path.name),
            caption=caption,
            reply_markup=reply_markup,
        )
        return

    chunks = _split_plain_caption(caption)
    for index, chunk in enumerate(chunks):
        await message.answer_photo(
            FSInputFile(path, filename=path.name),
            caption=chunk,
            reply_markup=reply_markup if index == len(chunks) - 1 else None,
        )
