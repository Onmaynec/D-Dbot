from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.button_ui.common import divider, esc, signed
from app.button_ui.keyboards import BTN_CHOICE
from app.button_ui.media import send_scene
from app.story_choices import StoryChoiceStore, StoryScenario


def _choice_keyboard(scenario: StoryScenario) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=option.title, callback_data=f"choice:resolve:{option.code}")]
        for option in scenario.options
    ]
    rows.append([InlineKeyboardButton(text="🔄 Другое событие после решения", callback_data="choice:open")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _next_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧭 Следующее событие", callback_data="choice:open")],
            [InlineKeyboardButton(text="⚔️ К бою", callback_data="combat:status")],
        ]
    )


def build_choices_router(store: StoryChoiceStore) -> Router:
    router = Router(name="button_story_choices_v5")

    async def show_choice(message: Message) -> None:
        scenario = await store.open(message.chat.id)
        option_lines = [
            f"{index}. <b>{esc(option.title)}</b>\n"
            f"Проверка: {option.ability} против сложности {option.difficulty}"
            for index, option in enumerate(scenario.options, 1)
        ]
        text = (
            f"🧭 <b>{esc(scenario.title)}</b>\n"
            "<i>Решение меняет награду и последствия для всей партии</i>\n\n"
            f"{esc(scenario.description)}\n\n"
            f"{divider()}\n"
            + "\n\n".join(option_lines)
            + "\n\n<i>Используется средняя характеристика всех героев партии. "
            "События нельзя решать во время активного боя.</i>"
        )
        await send_scene(message, scenario.scene, text, _choice_keyboard(scenario))

    @router.message(Command("choice"))
    @router.message(F.text == BTN_CHOICE)
    async def choice_entry(message: Message) -> None:
        await show_choice(message)

    @router.callback_query(F.data == "choice:open")
    async def choice_open(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_choice(callback.message)

    @router.callback_query(F.data.startswith("choice:resolve:"))
    async def choice_resolve(callback: CallbackQuery) -> None:
        option_code = callback.data.rsplit(":", 1)[1]
        result = await store.resolve(
            callback.message.chat.id,
            callback.from_user.id,
            option_code,
        )
        if not result.ok or result.scenario is None or result.option is None:
            await callback.answer(result.reason, show_alert=True)
            return
        await callback.answer("Решение принято")
        option = result.option
        if result.success:
            outcome_icon = "✅"
            outcome_text = option.success_text
        else:
            outcome_icon = "❌"
            outcome_text = option.failure_text
        consequences: list[str] = []
        if result.gold_delta:
            consequences.append(f"💰 Казна: {signed(result.gold_delta)} золота")
        if result.item_name:
            consequences.append(f"🎁 Получено: {esc(result.item_name)}")
        if result.damage_each:
            consequences.append(f"🩸 Каждый живой герой теряет {result.damage_each} HP")
        if not consequences:
            consequences.append("Партия проходит дальше без изменения ресурсов.")
        text = (
            f"{outcome_icon} <b>{esc(result.scenario.title)}</b>\n\n"
            f"Выбор: <b>{esc(option.title)}</b>\n"
            f"🎲 d20: {result.natural} {signed(result.modifier)} = <b>{result.total}</b> "
            f"против {option.difficulty}\n\n"
            f"{esc(outcome_text)}\n\n"
            f"{divider()}\n"
            + "\n".join(consequences)
            + f"\n💰 Текущая казна: <b>{result.balance} золота</b>"
        )
        scene = "loot_rare" if result.success and result.item_name else result.scenario.scene
        await send_scene(callback.message, scene, text, _next_keyboard())

    return router
