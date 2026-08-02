from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.battle_rewards import BattleRewardStore
from app.button_ui.common import esc
from app.button_ui.media import send_scene

REWARDS_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить награды", callback_data="rewards:show")],
        [InlineKeyboardButton(text="⚔️ К статусу боя", callback_data="combat:status")],
    ]
)


def build_rewards_router(reward_store: BattleRewardStore) -> Router:
    router = Router(name="button_rewards")

    async def show_rewards(message: Message) -> None:
        rewards = await reward_store.recent(message.chat.id, limit=10)
        if not rewards:
            text = (
                "🏆 <b>История побед пока пуста.</b>\n\n"
                "Заверши партийный бой, чтобы вся группа получила XP, "
                "золото в общую казну и трофей."
            )
        else:
            lines: list[str] = []
            for index, reward in enumerate(rewards, start=1):
                lines.append(
                    f"{index}. <b>Победа</b> · {esc(reward['created_at'])}\n"
                    f"   👥 {reward['party_size']} героев · "
                    f"✨ +{reward['xp_each']} XP каждому\n"
                    f"   💰 +{reward['gold']} золота · "
                    f"🎁 {esc(reward['item_name'])} ×{reward['quantity']}"
                )
            text = (
                "🏆 <b>Последние награды партии</b>\n\n"
                + "\n\n".join(lines)
                + "\n\nНаграда выдаётся автоматически в момент победы."
            )
        await send_scene(message, "loot_rare", text, REWARDS_MENU)

    @router.message(Command("rewards"))
    async def rewards_command(message: Message) -> None:
        await show_rewards(message)

    @router.callback_query(F.data == "rewards:show")
    async def rewards_refresh(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_rewards(callback.message)

    return router
