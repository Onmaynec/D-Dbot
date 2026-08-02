from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.button_ui.common import divider, esc, progress_bar, signed
from app.button_ui.keyboards import BTN_CASINO
from app.button_ui.media import send_scene
from app.casino import ALLOWED_BETS, CasinoStore

GAME_NAMES = {"coin": "Монета судьбы", "dice": "Кости крупье", "runes": "Рунный автомат"}
GAME_ICONS = {"coin": "🪙", "dice": "🎲", "runes": "🔮"}


def _casino_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for game in ("coin", "dice", "runes"):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{GAME_ICONS[game]} {bet}",
                    callback_data=f"casino:play:{game}:{bet}",
                )
                for bet in ALLOWED_BETS
            ]
        )
    rows.append([InlineKeyboardButton(text="📜 Последние игры", callback_data="casino:status")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _repeat_keyboard(game: str, bet: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🔁 Повторить ставку {bet}",
                    callback_data=f"casino:play:{game}:{bet}",
                )
            ],
            [InlineKeyboardButton(text="🎰 К столам", callback_data="casino:status")],
        ]
    )


def build_casino_router(store: CasinoStore) -> Router:
    router = Router(name="button_casino_v5")

    async def show_casino(message: Message) -> None:
        status = await store.status(message.chat.id)
        used = int(status["daily_stake"])
        limit = int(status["daily_limit"])
        text = (
            "🎰 <b>Таверна «Золотой мимик»</b>\n"
            "<i>Азартная зона на игровое золото</i>\n\n"
            f"💰 Общая казна: <b>{status['balance']} золота</b>\n"
            f"📊 Лимит ставок: {progress_bar(used, limit, 12)}  {used}/{limit}\n\n"
            f"{divider()}\n"
            "🪙 <b>Монета судьбы</b> — победа возвращает ставку ×2.\n"
            "🎲 <b>Кости крупье</b> — высокий бросок побеждает, ничья возвращает ставку.\n"
            "🔮 <b>Рунный автомат</b> — пара ×2, тройка ×5, три короны ×10.\n\n"
            "<i>Число на кнопке — размер ставки. Дневной лимит защищает общую казну от полного разорения.</i>"
        )
        await send_scene(message, "casino", text, _casino_keyboard())

    async def show_history(message: Message) -> None:
        status = await store.status(message.chat.id)
        history = status["history"]
        if not history:
            text = "🎰 <b>Столы ещё не открывались.</b>\n\nВыбери игру и ставку."
        else:
            lines = [
                "📜 <b>Последние игры</b>",
                f"💰 Казна: <b>{status['balance']} золота</b>",
                "",
            ]
            for row in history:
                game = GAME_NAMES.get(row["game"], row["game"])
                net = int(row["net"])
                lines.append(
                    f"{GAME_ICONS.get(row['game'], '🎰')} <b>{esc(game)}</b> · ставка {row['bet']}\n"
                    f"Результат: <b>{signed(net)} золота</b>"
                )
            text = "\n\n".join(lines)
        await send_scene(message, "casino", text, _casino_keyboard())

    @router.message(Command("casino"))
    @router.message(F.text == BTN_CASINO)
    async def casino_entry(message: Message) -> None:
        await show_casino(message)

    @router.callback_query(F.data == "casino:status")
    async def casino_status(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_history(callback.message)

    @router.callback_query(F.data.startswith("casino:play:"))
    async def casino_play(callback: CallbackQuery) -> None:
        _, _, game, bet_text = callback.data.split(":", 3)
        result = await store.play(
            callback.message.chat.id,
            callback.from_user.id,
            game,
            int(bet_text),
        )
        if not result.ok:
            await callback.answer(result.reason, show_alert=True)
            return
        await callback.answer("Ставка сыграна!")
        if result.net > 0:
            outcome_icon = "🏆"
            outcome = f"Выигрыш: <b>+{result.net} золота</b>"
        elif result.net == 0:
            outcome_icon = "🤝"
            outcome = "Ставка вернулась без прибыли."
        else:
            outcome_icon = "💸"
            outcome = f"Потеряно: <b>{result.net} золота</b>"
        text = (
            f"{GAME_ICONS.get(game, '🎰')} <b>{esc(GAME_NAMES.get(game, game))}</b>\n\n"
            f"{result.details}\n"
            f"{outcome_icon} <b>{esc(result.title)}</b>\n{outcome}\n\n"
            f"Ставка: {result.bet} · Выплата: {result.payout}\n"
            f"💰 Казна после игры: <b>{result.balance} золота</b>"
        )
        await send_scene(
            callback.message,
            "casino",
            text,
            _repeat_keyboard(game, result.bet),
        )

    return router
