from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.campaign_logic import (
    build_tracked_quest,
    generate_location,
    reputation_rank,
)
from app.campaign_progress import CampaignProgressStore
from app.database import Database
from app.generators import generate_quest
from app.session import SessionStore
from app.button_ui.common import campaign_context, esc
from app.button_ui.keyboards import (
    ACHIEVEMENTS_MENU,
    BTN_ACHIEVEMENTS,
    BTN_QUEST,
    BTN_REPUTATION,
    BTN_TRAVEL,
    QUEST_MENU,
    REPUTATION_MENU,
    TRAVEL_MENU,
    quest_detail_keyboard,
    quest_list_keyboard,
)
from app.button_ui.media import send_scene


def _quest_text(quest: dict) -> str:
    ready = int(quest["progress"]) >= int(quest["target"])
    state = "✅ готов к завершению" if ready else "⏳ выполняется"
    return (
        f"📜 <b>{esc(quest['title'])}</b>\n\n"
        f"Заказчик: {esc(quest['giver'])}\n"
        f"Цель: {esc(quest['goal'])}\n"
        f"Осложнение: <i>{esc(quest['complication'])}</i>\n\n"
        f"🎯 Прогресс: <b>{quest['progress']}/{quest['target']}</b> — {state}\n"
        f"🏛️ Фракция: {esc(quest['faction_name'])}\n"
        f"💰 Награда: {quest['gold_reward']} золотых, репутация +{quest['reputation_reward']}\n"
        f"🎁 Дополнительно: {esc(quest['reward_text'])}"
    )


def _achievement_notice(items: list[dict[str, str]]) -> str:
    if not items:
        return ""
    titles = ", ".join(esc(item["title"]) for item in items)
    return f"\n\n🏆 <b>Новое достижение:</b> {titles}"


def build_campaign_progress_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_campaign_progress")
    progress = CampaignProgressStore(database.path)

    async def faction_names(chat_id: int) -> list[str]:
        campaign = await store.get_campaign(chat_id)
        return list(campaign["factions"]) if campaign else []

    async def show_quests(message: Message) -> None:
        quests = await progress.list_quests(message.chat.id)
        if not quests:
            await send_scene(
                message,
                "quest",
                "📜 <b>Активных контрактов пока нет.</b>\n\n"
                "Возьми новый квест, выполняй его этапы и получай золото с репутацией.",
                QUEST_MENU,
            )
            return
        lines = [
            f"{index}. <b>{esc(quest['title'])}</b> — {quest['progress']}/{quest['target']}"
            for index, quest in enumerate(quests, 1)
        ]
        await send_scene(
            message,
            "quest",
            "📚 <b>Активные квесты</b>\n\n" + "\n".join(lines),
            quest_list_keyboard(quests),
        )

    async def show_quest(message: Message, quest_id: int) -> None:
        quest = await progress.get_quest(message.chat.id, quest_id)
        if not quest or quest["status"] != "active":
            await send_scene(message, "quest", "⚠️ Этот контракт больше не активен.", QUEST_MENU)
            return
        await send_scene(message, "quest", _quest_text(quest), quest_detail_keyboard(quest))

    async def show_current_location(message: Message) -> None:
        location = await progress.get_location(message.chat.id)
        if not location:
            await send_scene(
                message,
                "campaign",
                "🗺️ <b>Карта ещё пуста.</b>\n\nОтправься в первое путешествие, чтобы открыть локацию.",
                TRAVEL_MENU,
            )
            return
        await send_scene(
            message,
            "campaign",
            f"📍 <b>{esc(location['name'])}</b>\n\n"
            f"Местность: {esc(location['biome'])}\n"
            f"Опасность: {esc(location['danger'])}\n"
            f"Находка: {esc(location['discovery'])}\n"
            f"Влияние: {esc(location['faction_name'])}",
            TRAVEL_MENU,
        )

    async def show_reputation(message: Message) -> None:
        factions = await faction_names(message.chat.id)
        reputation = await progress.get_reputation(message.chat.id, factions)
        if not reputation:
            body = "Начни кампанию, чтобы появились фракции и политические отношения."
        else:
            body = "\n\n".join(
                f"🏛️ <b>{esc(name)}</b>\n{score:+d} · {reputation_rank(score)}"
                for name, score in sorted(reputation.items())
            )
        await send_scene(
            message,
            "campaign",
            "🏛️ <b>Репутация партии</b>\n\n" + body,
            REPUTATION_MENU,
        )

    async def show_achievements(message: Message) -> None:
        factions = await faction_names(message.chat.id)
        achievements, newly = await progress.refresh_achievements(message.chat.id, factions)
        stats = await progress.get_stats(message.chat.id)
        if achievements:
            body = "\n\n".join(
                f"🏆 <b>{esc(item['title'])}</b>\n{esc(item['description'])}"
                for item in achievements
            )
        else:
            body = "Пока ни одна легенда не высечена в камне."
        await send_scene(
            message,
            "journal",
            "🏆 <b>Достижения кампании</b>\n\n"
            f"Квестов завершено: {stats['quests_completed']}\n"
            f"Локаций открыто: {stats['locations_visited']}\n"
            f"Этапов выполнено: {stats['quest_steps']}\n\n{body}"
            + _achievement_notice(newly),
            ACHIEVEMENTS_MENU,
        )

    @router.message(F.text == BTN_QUEST)
    async def quest_button(message: Message) -> None:
        await show_quests(message)

    @router.callback_query(F.data == "quest:new")
    async def new_quest(callback: CallbackQuery) -> None:
        await callback.answer("Новый контракт получен")
        campaign, suffix = await campaign_context(store, callback.message.chat.id)
        generated = generate_quest(campaign["name"] if campaign else None)
        factions = list(campaign["factions"]) if campaign else []
        tracked = build_tracked_quest(generated, factions)
        quest_id = await progress.add_quest(callback.message.chat.id, tracked)
        quest = await progress.get_quest(callback.message.chat.id, quest_id)
        await store.log(
            callback.message.chat.id,
            "quest",
            f"Принят контракт: {tracked['goal']} для фракции {tracked['faction_name']}",
            payload=tracked,
        )
        await send_scene(
            callback.message,
            "quest",
            _quest_text(quest) + suffix,
            quest_detail_keyboard(quest),
        )

    @router.callback_query(F.data == "quest:list")
    async def quest_list(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_quests(callback.message)

    @router.callback_query(F.data.startswith("quest:view:"))
    async def quest_view(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_quest(callback.message, int(callback.data.rsplit(":", 1)[1]))

    @router.callback_query(F.data.startswith("quest:advance:"))
    async def quest_advance(callback: CallbackQuery) -> None:
        await callback.answer("Этап выполнен")
        quest_id = int(callback.data.rsplit(":", 1)[1])
        quest = await progress.advance_quest(callback.message.chat.id, quest_id)
        if not quest:
            await send_scene(callback.message, "quest", "⚠️ Контракт не найден.", QUEST_MENU)
            return
        await store.log(
            callback.message.chat.id,
            "quest_progress",
            f"Квест «{quest['title']}»: {quest['progress']}/{quest['target']}",
        )
        await send_scene(callback.message, "quest", _quest_text(quest), quest_detail_keyboard(quest))

    @router.callback_query(F.data.startswith("quest:complete:"))
    async def quest_complete(callback: CallbackQuery) -> None:
        quest_id = int(callback.data.rsplit(":", 1)[1])
        quest = await progress.complete_quest(callback.message.chat.id, quest_id)
        if not quest:
            await callback.answer("Сначала выполни все этапы", show_alert=True)
            return
        await callback.answer("Контракт завершён!")
        gold = await database.add_gold(callback.message.chat.id, int(quest["gold_reward"]))
        reputation = await progress.adjust_reputation(
            callback.message.chat.id,
            quest["faction_name"],
            int(quest["reputation_reward"]),
        )
        factions = await faction_names(callback.message.chat.id)
        _, newly = await progress.refresh_achievements(callback.message.chat.id, factions)
        await store.log(
            callback.message.chat.id,
            "quest_complete",
            f"Завершён контракт «{quest['title']}»: +{quest['gold_reward']} золота",
            payload=quest,
        )
        await send_scene(
            callback.message,
            "loot_rare",
            f"✅ <b>Контракт завершён</b>\n\n{esc(quest['title'])}\n"
            f"💰 Получено: {quest['gold_reward']} золотых\n"
            f"🏦 Казна: {gold} золотых\n"
            f"🏛️ {esc(quest['faction_name'])}: {reputation:+d} ({reputation_rank(reputation)})\n"
            f"🎁 {esc(quest['reward_text'])}"
            + _achievement_notice(newly),
            QUEST_MENU,
        )

    @router.callback_query(F.data.startswith("quest:abandon:"))
    async def quest_abandon(callback: CallbackQuery) -> None:
        quest_id = int(callback.data.rsplit(":", 1)[1])
        abandoned = await progress.abandon_quest(callback.message.chat.id, quest_id)
        await callback.answer("Контракт оставлен" if abandoned else "Контракт уже закрыт")
        await show_quests(callback.message)

    @router.message(F.text == BTN_TRAVEL)
    async def travel_button(message: Message) -> None:
        await show_current_location(message)

    @router.callback_query(F.data == "travel:where")
    async def travel_where(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_current_location(callback.message)

    @router.callback_query(F.data == "travel:go")
    async def travel_go(callback: CallbackQuery) -> None:
        await callback.answer("Путь начинается")
        campaign = await store.get_campaign(callback.message.chat.id)
        location = generate_location(campaign)
        visits = await progress.save_location(callback.message.chat.id, location)
        gold = await database.add_gold(callback.message.chat.id, int(location["gold_found"]))
        reputation_note = ""
        if int(location["reputation_delta"]):
            score = await progress.adjust_reputation(
                callback.message.chat.id,
                location["faction_name"],
                int(location["reputation_delta"]),
            )
            reputation_note = (
                f"\n🏛️ Репутация с {esc(location['faction_name'])}: {score:+d}"
            )

        quest_note = ""
        active = await progress.list_quests(callback.message.chat.id)
        pending = next(
            (quest for quest in reversed(active) if int(quest["progress"]) < int(quest["target"])),
            None,
        )
        if pending:
            quest = await progress.advance_quest(callback.message.chat.id, int(pending["id"]))
            if quest:
                quest_note = (
                    f"\n🎯 Квест «{esc(quest['title'])}»: {quest['progress']}/{quest['target']}"
                )

        factions = list(campaign["factions"]) if campaign else []
        _, newly = await progress.refresh_achievements(callback.message.chat.id, factions)
        await store.log(
            callback.message.chat.id,
            "travel",
            f"Открыта локация {location['name']}: {location['discovery']}",
            payload=location,
        )
        await send_scene(
            callback.message,
            "campaign",
            f"🗺️ <b>{esc(location['name'])}</b>\n\n"
            f"Местность: {esc(location['biome'])}\n"
            f"Опасность: {esc(location['danger'])}\n"
            f"Находка: <b>{esc(location['discovery'])}</b>\n"
            f"Влияние: {esc(location['faction_name'])}\n\n"
            f"💰 Найдено {location['gold_found']} золотых · казна {gold}\n"
            f"📍 Открыто локаций: {visits}"
            f"{quest_note}{reputation_note}"
            + _achievement_notice(newly),
            TRAVEL_MENU,
        )

    @router.message(F.text == BTN_REPUTATION)
    async def reputation_button(message: Message) -> None:
        await show_reputation(message)

    @router.callback_query(F.data == "reputation:show")
    async def reputation_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_reputation(callback.message)

    @router.message(F.text == BTN_ACHIEVEMENTS)
    async def achievements_button(message: Message) -> None:
        await show_achievements(message)

    @router.callback_query(F.data == "achievements:show")
    async def achievements_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_achievements(callback.message)

    return router
