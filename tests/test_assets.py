from pathlib import Path

EXPECTED_IMAGES = {
    "start.jpg", "campaign.jpg", "character.jpg", "quest.jpg", "npc.jpg",
    "encounter_friendly.jpg", "encounter_neutral.jpg", "encounter_hostile.jpg",
    "combat.jpg", "attack.jpg", "spell.jpg", "rest.jpg", "levelup.jpg",
    "loot_common.jpg", "loot_rare.jpg", "journal.jpg", "journal_thumb.jpg",
}


def test_all_game_images_are_present() -> None:
    assets = Path("assets/images")
    assert EXPECTED_IMAGES <= {path.name for path in assets.glob("*.jpg")}


def test_game_images_are_not_empty() -> None:
    assets = Path("assets/images")
    for filename in EXPECTED_IMAGES:
        assert (assets / filename).stat().st_size > 1_000
