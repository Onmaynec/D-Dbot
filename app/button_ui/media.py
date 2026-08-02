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
    "start": "Start.png",
    "campaign": "campaign.png",
    "character": "character.png",
    "equipment": "character.png",
    "quest": "quest.png",
    "choice": "encounter_neutral.png",
    "npc": "npc.png",
    "encounter_friendly": "encounter_friendly.png",
    "encounter_neutral": "encounter_neutral.png",
    "encounter_hostile": "encounter_hostile.png",
    "combat": "combat.png",
    "attack": "attack.png",
    "spell": "spell.png",
    "rest": "rest.png",
    "levelup": "levelup.png",
    "loot_common": "loot_common.png",
    "loot_rare": "loot_rare.png",
    "casino": "loot_rare.png",
    "journal": "journal.png",
}

LEGACY_SCENE_FILES = {
    scene: ("start.jpg" if scene == "start" else filename.replace(".png", ".jpg").replace("Start.jpg", "start.jpg"))
    for scene, filename in SCENE_FILES.items()
}

ImageModeResolver = Callable[[int], Awaitable[str]]
_image_mode_resolver: ImageModeResolver | None = None


def configure_image_mode_resolver(resolver: ImageModeResolver | None) -> None:
    global _image_mode_resolver
    _image_mode_resolver = resolver


def ensure_fallback_assets() -> None:
    GENERATED_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, encoded in IMAGE_DATA.items():
        path = GENERATED_ASSETS_DIR / filename
        if not path.exists() or path.stat().st_size == 0:
            path.write_bytes(base64.b64decode(encoded))


def ensure_upscaled_assets() -> None:
    """Оставляет совместимость со старыми JPG, когда новые PNG ещё не установлены."""
    ensure_fallback_assets()
    UPSCALED_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for filename in set(LEGACY_SCENE_FILES.values()):
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
                continue


def scene_path(scene: str) -> Path:
    resolved_scene = scene if scene in SCENE_FILES else "start"
    png_name = SCENE_FILES[resolved_scene]
    source_png = SOURCE_ASSETS_DIR / png_name
    if source_png.exists() and source_png.stat().st_size > 100_000:
        return source_png

    legacy_name = LEGACY_SCENE_FILES[resolved_scene]
    source_legacy = SOURCE_ASSETS_DIR / legacy_name
    if source_legacy.exists() and source_legacy.stat().st_size > 35_000:
        return source_legacy

    ensure_upscaled_assets()
    upscaled = UPSCALED_ASSETS_DIR / legacy_name
    if upscaled.exists() and upscaled.stat().st_size > 35_000:
        return upscaled

    ensure_fallback_assets()
    return GENERATED_ASSETS_DIR / legacy_name


def journal_thumbnail() -> FSInputFile:
    path = scene_path("journal")
    return FSInputFile(path, filename=path.name)


def _plain_text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value))


def _split_plain_caption(value: str, limit: int = 4096) -> list[str]:
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
        return "document"
    try:
        mode = await _image_mode_resolver(chat_id)
    except Exception:
        return "document"
    return mode if mode in {"photo", "document"} else "document"


async def _send_text(
    message: Message,
    text: str,
    reply_markup: Any | None,
) -> None:
    if len(text) <= 4096:
        await message.answer(text, reply_markup=reply_markup)
        return
    chunks = _split_plain_caption(text)
    for index, chunk in enumerate(chunks):
        await message.answer(
            chunk,
            reply_markup=reply_markup if index == len(chunks) - 1 else None,
        )


async def send_scene(
    message: Message,
    scene: str,
    caption: str,
    reply_markup: Any | None = None,
) -> None:
    """Отправляет PNG как документ без потерь либо как быстрое Telegram-фото."""
    path = scene_path(scene)
    mode = await _resolve_image_mode(message.chat.id)

    if mode == "document":
        await message.answer_document(FSInputFile(path, filename=path.name))
        await _send_text(message, caption, reply_markup)
        return

    if len(caption) <= 1024:
        await message.answer_photo(
            FSInputFile(path, filename=path.name),
            caption=caption,
            reply_markup=reply_markup,
        )
        return

    await message.answer_photo(FSInputFile(path, filename=path.name))
    await _send_text(message, caption, reply_markup)
