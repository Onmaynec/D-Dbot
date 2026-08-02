from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app import __version__
from app.battle_rewards import BattleRewardStore
from app.button_ui.adventure import build_adventure_router
from app.button_ui.campaign_progress import build_campaign_progress_router
from app.button_ui.casino import build_casino_router
from app.button_ui.choices import build_choices_router
from app.button_ui.combat import build_combat_router
from app.button_ui.combat_choices import build_combat_choices_router
from app.button_ui.daily import build_daily_router
from app.button_ui.dungeon import build_dungeon_router
from app.button_ui.equipment import build_equipment_router
from app.button_ui.forge import build_forge_router
from app.button_ui.journal import build_journal_router
from app.button_ui.keyboards import MAIN_MENU
from app.button_ui.media import configure_image_mode_resolver, send_scene
from app.button_ui.progression import build_progression_router
from app.button_ui.rewards import build_rewards_router
from app.button_ui.support import build_support_router
from app.button_ui.tactical import build_tactical_router
from app.casino import CasinoStore
from app.combat_choices import CombatChoiceStore
from app.daily_rewards import DailyRewardStore
from app.database import Database
from app.dungeon_store import DungeonStore
from app.equipment import EquipmentStore
from app.maintenance import check_database, format_bytes
from app.party_support import PartySupportStore
from app.session import SessionStore
from app.story_choices import StoryChoiceStore
from app.tactical_items import TacticalItemStore
from app.v5_migrations import apply_v5_chat_defaults


def build_button_router(database: Database, store: SessionStore) -> Router:
    router = Router(name="button_ui")
    dungeon_store = DungeonStore(database.path)
    daily_store = DailyRewardStore(database.path)
    tactical_store = TacticalItemStore(database.path)
    support_store = PartySupportStore(database.path)
    reward_store = BattleRewardStore(database.path)
    equipment_store = EquipmentStore(database.path)
    casino_store = CasinoStore(database.path)
    choice_store = StoryChoiceStore(database.path)
    combat_choice_store = CombatChoiceStore(database.path)
    configure_image_mode_resolver(dungeon_store.get_image_mode)

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        hq_enabled = await apply_v5_chat_defaults(database.path, message.chat.id)
        quality_note = (
            "\n💎 Для этого чата включена отправка PNG без сжатия."
            if hq_enabled
            else ""
        )
        await send_scene(
            message,
            "start",
            f"🐉 <b>D&D Telegram Master v{__version__}</b>\n"
            "<i>Adventure Reforged</i>\n\n"
            "<b>Быстрый старт</b>\n"
            "1️⃣ Создай мир через «🏕️ Кампания».\n"
            "2️⃣ Создай героя и вступи в «👥 Партию».\n"
            "3️⃣ Купи оружие и броню в «🧰 Снаряжение».\n"
            "4️⃣ Выбирай сюжетные решения, исследуй подземелья и сражайся вместе.\n\n"
            "<b>Главные новинки v5</b>\n"
            "⚔️ Рискованные удары и защитная стойка\n"
            "🧰 Оружие, броня и талисманы\n"
            "🧭 Сюжетные события с тремя вариантами\n"
            "🎰 Казино на игровое золото\n"
            "🖼️ Новые полноразмерные сцены"
            f"{quality_note}\n\n"
            "Нижняя клавиатура разделена по понятным игровым системам.",
            MAIN_MENU,
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await send_scene(
            message,
            "journal",
            "❓ <b>Как устроена игра</b>\n\n"
            "<b>Развитие героя</b>\n"
            "• /equipment — купить и надеть оружие, броню или талисман.\n"
            "• Победы дают XP каждому участнику, золото и общий трофей.\n"
            "• /rewards — история наград партии.\n\n"
            "<b>Партийный бой</b>\n"
            "• Каждый живой игрок действует один раз за раунд.\n"
            "• Обычная атака надёжна; рискованный удар получает −2 к попаданию и +4 к урону.\n"
            "• Защитная стойка повышает КД и ослабляет входящий удар.\n"
            "• /support лечит союзника, /tactics активирует боевые реликвии.\n"
            "• /actions открывает все варианты боевого хода.\n\n"
            "<b>Приключения</b>\n"
            "• /choice — событие с тремя решениями и проверкой характеристик всей партии.\n"
            "• Подземелья, контракты, путешествия и фракции сохраняются между запусками.\n\n"
            "<b>Экономика</b>\n"
            "• /daily — ежедневная награда, /forge — крафт.\n"
            "• /casino — монета, кости и рунный автомат на игровое золото.\n"
            "• Казино имеет дневной лимит ставок, чтобы не уничтожить общую казну.\n\n"
            "<b>Изображения</b>\n"
            "В настройках доступны быстрые фото и исходные PNG без сжатия.",
            MAIN_MENU,
        )

    @router.message(Command("status"))
    async def status_handler(message: Message) -> None:
        health = await check_database(database.path)
        icon = "✅" if health.ok else "⚠️"
        await message.answer(
            f"🩺 <b>D&D Telegram Master v{__version__}</b>\n"
            "<i>Adventure Reforged</i>\n\n"
            f"{icon} SQLite: {health.message}\n"
            f"💾 Размер данных: {format_bytes(health.size_bytes)}\n"
            "🧰 Экипировка: активна\n"
            "🎰 Казино: активно\n"
            "🧭 Сюжетные решения: активны\n"
            "🛡️ Резервная копия создаётся при запуске."
        )

    router.include_router(build_dungeon_router(database, store, dungeon_store))
    router.include_router(build_daily_router(store, daily_store))
    router.include_router(build_forge_router(database, store))
    router.include_router(build_tactical_router(database, store, tactical_store))
    router.include_router(build_support_router(database, store, support_store))
    router.include_router(build_rewards_router(reward_store))
    router.include_router(build_equipment_router(equipment_store))
    router.include_router(build_casino_router(casino_store))
    router.include_router(build_choices_router(choice_store))
    router.include_router(
        build_combat_choices_router(database, store, combat_choice_store)
    )
    router.include_router(build_progression_router(database, store))
    router.include_router(build_campaign_progress_router(database, store))
    router.include_router(build_adventure_router(database, store))
    router.include_router(build_combat_router(database, store))
    router.include_router(build_journal_router(database, store))
    return router
