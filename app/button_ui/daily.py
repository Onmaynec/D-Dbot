from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.button_ui.common import esc
from app.button_ui.keyboards import MAIN_MENU
from app.button_ui.media import send_scene
from app.daily_rewards import DailyReward, DailyRewardStore
from app.session import SessionStore

DAILY_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Получить награду", callback_data="daily:claim")],
        [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="daily:status")],
    ]
)


def reward_text(reward: DailyReward) -> str:
    lines = [f"💰 {reward.gold} золотых"]
    if reward.item_name:
        lines.append(f"🎒 {esc(reward.item_name)} ({esc(reward.item_rarity or 'обычная')})")
    return "\n".join(lines)


def build_daily_router(session_store: SessionStore, daily_store: DailyRewardStore) -> Router:
    router = Router(name="button_daily_rewards")

    async def show_status(message: Message) -> None:
        status = await daily_store.get_status(message.chat.id)
        if status.claimed_today:
            body = (
                "✅ <b>Сегодняшняя награда уже получена.</b>\n\n"
                f"🔥 Текущая серия: <b>{status.streak}</b>\n"
                f"🏆 Всего получений: {status.total_claims}\n"
                f"📅 Следующая награда: {status.next_claim_date.strftime('%d.%m.%Y')} (UTC)\n\n"
                f"<b>Предпросмотр следующей:</b>\n{reward_text(status.preview)}"
            )
        else:
            body = (
                "🎁 <b>Ежедневная награда готова!</b>\n\n"
                f"🔥 Следующий день серии: <b>{status.next_streak}</b>\n"
                f"🏆 Всего получений: {status.total_claims}\n\n"
                f"<b>Сегодня в сундуке:</b>\n{reward_text(status.preview)}\n\n"
                "Серия растёт при получении награды каждый день. На 3-й день выдаётся бонусный предмет, "
                "а на 7-й — эпический жетон судьбы."
            )
        await send_scene(message, "loot_rare", body, DAILY_MENU)

    @router.message(Command("daily"))
    async def daily_command(message: Message) -> None:
        await show_status(message)

    @router.callback_query(F.data == "daily:status")
    async def daily_status(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_status(callback.message)

    @router.callback_query(F.data == "daily:claim")
    async def daily_claim(callback: CallbackQuery) -> None:
        result = await daily_store.claim(callback.message.chat.id, callback.from_user.id)
        if not result.claimed or result.reward is None:
            await callback.answer("Сегодня награда уже получена партией.", show_alert=True)
            await show_status(callback.message)
            return

        reward = result.reward
        await session_store.log(
            callback.message.chat.id,
            "daily_reward",
            f"Получена ежедневная награда: {reward.gold} золотых, серия {result.streak}",
            payload={
                "gold": reward.gold,
                "item_name": reward.item_name,
                "item_rarity": reward.item_rarity,
                "streak": result.streak,
                "total_claims": result.total_claims,
                "claimed_by": callback.from_user.id,
            },
        )
        await callback.answer("Награда добавлена в казну!")
        await send_scene(
            callback.message,
            "loot_rare",
            "🎉 <b>Ежедневный сундук открыт!</b>\n\n"
            f"{reward_text(reward)}\n\n"
            f"🔥 Серия: <b>{result.streak}</b>\n"
            f"💰 В казне теперь: <b>{result.gold_balance}</b> золотых\n"
            f"📅 Следующее получение: {result.next_claim_date.strftime('%d.%m.%Y')} (UTC)",
            MAIN_MENU,
        )

    return router
