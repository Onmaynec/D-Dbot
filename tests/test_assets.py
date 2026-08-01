from __future__ import annotations

import base64

from app.button_ui.image_data_0 import IMAGE_DATA_0
from app.button_ui.image_data_1 import IMAGE_DATA_1
from app.button_ui.image_data_2 import IMAGE_DATA_2
from app.button_ui.image_data_3 import IMAGE_DATA_3
from app.button_ui.image_data_4 import IMAGE_DATA_4

EXPECTED_IMAGES = {
    "start.jpg", "campaign.jpg", "character.jpg", "quest.jpg", "npc.jpg",
    "encounter_friendly.jpg", "encounter_neutral.jpg", "encounter_hostile.jpg",
    "combat.jpg", "attack.jpg", "spell.jpg", "rest.jpg", "levelup.jpg",
    "loot_common.jpg", "loot_rare.jpg", "journal.jpg", "journal_thumb.jpg",
}


def all_images() -> dict[str, str]:
    images: dict[str, str] = {}
    for group in (IMAGE_DATA_0, IMAGE_DATA_1, IMAGE_DATA_2, IMAGE_DATA_3, IMAGE_DATA_4):
        images.update(group)
    return images


def test_all_game_images_are_embedded() -> None:
    assert set(all_images()) == EXPECTED_IMAGES


def test_embedded_images_are_valid_jpeg_files() -> None:
    for encoded in all_images().values():
        raw = base64.b64decode(encoded)
        assert len(raw) > 1_000
        assert raw.startswith(b"\xff\xd8")
        assert raw.endswith(b"\xff\xd9")
