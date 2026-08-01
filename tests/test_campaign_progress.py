import random

from app.campaign_logic import (
    achievement_candidates,
    advance_progress,
    build_tracked_quest,
    generate_location,
    reputation_rank,
)


def test_tracked_quest_has_progress_target_and_faction() -> None:
    quest = {
        "giver": "архивариус",
        "goal": "найти утерянную карту",
        "reward": "редкий свиток",
        "complication": "за героями следят",
    }
    tracked = build_tracked_quest(quest, ["Орден Рассвета"], random.Random(4))
    assert tracked["faction_name"] == "Орден Рассвета"
    assert tracked["progress"] == 0
    assert 2 <= tracked["target"] <= 4
    assert tracked["gold_reward"] > 0


def test_advance_progress_is_capped() -> None:
    assert advance_progress(2, 3, 5) == 3
    assert advance_progress(0, 3) == 1


def test_location_uses_campaign_faction() -> None:
    campaign = {"factions": ["Конклав Картографов"]}
    location = generate_location(campaign, random.Random(7))
    assert location["faction_name"] == "Конклав Картографов"
    assert location["gold_found"] >= 5


def test_reputation_rank_thresholds() -> None:
    assert reputation_rank(0) == "нейтрально"
    assert reputation_rank(4) == "союзники"
    assert reputation_rank(-4) == "враждебность"


def test_achievement_candidates_follow_campaign_stats() -> None:
    achievements = achievement_candidates(
        {"quests_completed": 5, "locations_visited": 3, "quest_steps": 12},
        {"Орден": 3},
    )
    codes = {item["code"] for item in achievements}
    assert {"first_contract", "pathfinder", "trusted_ally", "quest_veteran"} <= codes
