from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

BTN_CAMPAIGN = "🏕️ Кампания"
BTN_PARTY = "👥 Партия"
BTN_CHARACTER = "🧙 Герой"
BTN_INVENTORY = "🎒 Инвентарь"
BTN_QUEST = "📜 Квест"
BTN_NPC = "🎭 NPC"
BTN_ENCOUNTER = "🌍 Встреча"
BTN_LOOT = "💎 Добыча"
BTN_COMBAT = "⚔️ Бой"
BTN_DICE = "🎲 Кубы"
BTN_MAGIC = "✨ Магия"
BTN_REST = "🛌 Отдых"
BTN_SHOP = "🏪 Лавка"
BTN_JOURNAL = "📖 Журнал"
BTN_MORE = "⚙️ Ещё"
BTN_CANCEL = "❌ Отмена"

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_CAMPAIGN), KeyboardButton(text=BTN_PARTY)],
        [KeyboardButton(text=BTN_CHARACTER), KeyboardButton(text=BTN_INVENTORY)],
        [KeyboardButton(text=BTN_QUEST), KeyboardButton(text=BTN_NPC)],
        [KeyboardButton(text=BTN_ENCOUNTER), KeyboardButton(text=BTN_LOOT)],
        [KeyboardButton(text=BTN_COMBAT), KeyboardButton(text=BTN_MAGIC)],
        [KeyboardButton(text=BTN_DICE), KeyboardButton(text=BTN_REST)],
        [KeyboardButton(text=BTN_SHOP), KeyboardButton(text=BTN_JOURNAL)],
        [KeyboardButton(text=BTN_MORE)],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Выбери действие в приключении…",
)

CANCEL_MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
    resize_keyboard=True,
    one_time_keyboard=True,
    input_field_placeholder="Введи текст или отмени действие…",
)

CAMPAIGN_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✨ Начать новую кампанию", callback_data="campaign:new")],
    [InlineKeyboardButton(text="📖 Показать текущую", callback_data="campaign:show")],
])

CHARACTER_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎲 Создать нового героя", callback_data="character:new")],
    [InlineKeyboardButton(text="📋 Показать героя", callback_data="character:show")],
    [InlineKeyboardButton(text="⬆️ Повысить уровень", callback_data="levelup:check")],
])

PARTY_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Вступить в партию", callback_data="party:join")],
    [InlineKeyboardButton(text="👥 Показать состав", callback_data="party:show")],
    [InlineKeyboardButton(text="🚪 Покинуть партию", callback_data="party:leave")],
])

DICE_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="d4", callback_data="dice:d4"), InlineKeyboardButton(text="d6", callback_data="dice:d6"), InlineKeyboardButton(text="d8", callback_data="dice:d8")],
    [InlineKeyboardButton(text="d10", callback_data="dice:d10"), InlineKeyboardButton(text="d12", callback_data="dice:d12"), InlineKeyboardButton(text="d20", callback_data="dice:d20")],
    [InlineKeyboardButton(text="d100", callback_data="dice:d100"), InlineKeyboardButton(text="2d6", callback_data="dice:2d6"), InlineKeyboardButton(text="d20+3", callback_data="dice:d20+3")],
])

SPELL_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔥 Огненный шар", callback_data="spell:Огненный шар"), InlineKeyboardButton(text="❄️ Ледяное копьё", callback_data="spell:Ледяное копьё")],
    [InlineKeyboardButton(text="⚡ Цепная молния", callback_data="spell:Цепная молния"), InlineKeyboardButton(text="🌑 Теневой луч", callback_data="spell:Теневой луч")],
    [InlineKeyboardButton(text="✍️ Назвать своё заклинание", callback_data="spell:custom")],
])

COMBAT_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⚔️ Начать новый бой", callback_data="combat:start")],
    [InlineKeyboardButton(text="🗡️ Атаковать", callback_data="combat:attack"), InlineKeyboardButton(text="✨ Заклинание", callback_data="combat:spell")],
    [InlineKeyboardButton(text="🛡️ Статус боя", callback_data="combat:status")],
])

MORE_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬆️ Повышение уровня", callback_data="levelup:check")],
    [InlineKeyboardButton(text="📤 Экспорт журнала TXT", callback_data="journal:export")],
    [InlineKeyboardButton(text="❓ Как играть", callback_data="menu:help")],
])

JOURNAL_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Обновить журнал", callback_data="journal:show")],
    [InlineKeyboardButton(text="📤 Экспортировать TXT", callback_data="journal:export")],
])

INVENTORY_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Обновить инвентарь", callback_data="inventory:show")],
    [InlineKeyboardButton(text="🏪 Открыть лавку", callback_data="shop:show")],
])


def attack_targets_keyboard(state: dict[str, Any]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for enemy in state.get("enemies", []):
        if enemy.get("alive", True) and enemy.get("hp", 0) > 0:
            rows.append([InlineKeyboardButton(
                text=f"🗡️ {enemy['id']}. {enemy['name']} ({enemy['hp']} HP)",
                callback_data=f"attack:{enemy['id']}",
            )])
    rows.append([InlineKeyboardButton(text="🛡️ Статус боя", callback_data="combat:status")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def levelup_keyboard(character_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💪 Сила", callback_data=f"lvl:{character_id}:str"), InlineKeyboardButton(text="🏹 Ловкость", callback_data=f"lvl:{character_id}:dex")],
        [InlineKeyboardButton(text="🔮 Мудрость", callback_data=f"lvl:{character_id}:wis"), InlineKeyboardButton(text="❤️ Живучесть", callback_data=f"lvl:{character_id}:vit")],
    ])


def inventory_keyboard(items: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    consumables = {"Зелье лечения": 0, "Большое зелье лечения": 1}
    for item in items:
        name = str(item["item_name"])
        if name in consumables and int(item["quantity"]) > 0:
            rows.append([InlineKeyboardButton(
                text=f"🧪 Использовать: {name}", callback_data=f"inventory:use:{consumables[name]}"
            )])
    rows.extend([
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="inventory:show")],
        [InlineKeyboardButton(text="🏪 Открыть лавку", callback_data="shop:show")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_keyboard(items: tuple[dict[str, Any], ...]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"🛒 {item['name']} — {item['price']} зм.", callback_data=f"shop:buy:{index}"
        )]
        for index, item in enumerate(items)
    ]
    rows.append([InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory:show")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
