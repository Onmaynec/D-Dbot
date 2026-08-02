from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

BTN_CAMPAIGN = "🏕️ Кампания"
BTN_PARTY = "👥 Партия"
BTN_CHARACTER = "🧙 Герой"
BTN_EQUIPMENT = "🧰 Снаряжение"
BTN_INVENTORY = "🎒 Инвентарь"
BTN_QUEST = "📜 Квесты"
BTN_CHOICE = "🧭 Решение"
BTN_TRAVEL = "🗺️ Путешествие"
BTN_DUNGEON = "🏰 Подземелье"
BTN_NPC = "🎭 NPC"
BTN_ENCOUNTER = "🌍 Встреча"
BTN_LOOT = "💎 Добыча"
BTN_COMBAT = "⚔️ Бой"
BTN_DICE = "🎲 Кубы"
BTN_CASINO = "🎰 Казино"
BTN_MAGIC = "✨ Магия"
BTN_REST = "🛌 Отдых"
BTN_SHOP = "🏪 Лавка"
BTN_REPUTATION = "🏛️ Репутация"
BTN_ACHIEVEMENTS = "🏆 Достижения"
BTN_SETTINGS = "🎛️ Настройки"
BTN_JOURNAL = "📖 Журнал"
BTN_MORE = "⚙️ Ещё"
BTN_CANCEL = "❌ Отмена"

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_CAMPAIGN), KeyboardButton(text=BTN_PARTY)],
        [KeyboardButton(text=BTN_CHARACTER), KeyboardButton(text=BTN_EQUIPMENT)],
        [KeyboardButton(text=BTN_QUEST), KeyboardButton(text=BTN_CHOICE)],
        [KeyboardButton(text=BTN_TRAVEL), KeyboardButton(text=BTN_DUNGEON)],
        [KeyboardButton(text=BTN_COMBAT), KeyboardButton(text=BTN_MAGIC)],
        [KeyboardButton(text=BTN_INVENTORY), KeyboardButton(text=BTN_SHOP)],
        [KeyboardButton(text=BTN_NPC), KeyboardButton(text=BTN_ENCOUNTER)],
        [KeyboardButton(text=BTN_LOOT), KeyboardButton(text=BTN_CASINO)],
        [KeyboardButton(text=BTN_DICE), KeyboardButton(text=BTN_REST)],
        [KeyboardButton(text=BTN_REPUTATION), KeyboardButton(text=BTN_ACHIEVEMENTS)],
        [KeyboardButton(text=BTN_JOURNAL), KeyboardButton(text=BTN_SETTINGS)],
        [KeyboardButton(text=BTN_MORE)],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Выбери следующий шаг приключения…",
)

CANCEL_MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
    resize_keyboard=True,
    one_time_keyboard=True,
    input_field_placeholder="Введи текст или отмени действие…",
)

CAMPAIGN_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✨ Начать новую кампанию", callback_data="campaign:new")],
        [InlineKeyboardButton(text="📖 Показать текущую", callback_data="campaign:show")],
    ]
)

CHARACTER_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Создать нового героя", callback_data="character:new")],
        [InlineKeyboardButton(text="📋 Показать героя", callback_data="character:show")],
        [InlineKeyboardButton(text="🧰 Снаряжение", callback_data="eq:show")],
        [InlineKeyboardButton(text="⬆️ Повысить уровень", callback_data="levelup:check")],
    ]
)

PARTY_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="➕ Вступить в партию", callback_data="party:join")],
        [InlineKeyboardButton(text="👥 Показать состав", callback_data="party:show")],
        [InlineKeyboardButton(text="🚪 Покинуть партию", callback_data="party:leave")],
    ]
)

QUEST_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✨ Получить новый контракт", callback_data="quest:new")],
        [InlineKeyboardButton(text="📚 Активные квесты", callback_data="quest:list")],
        [InlineKeyboardButton(text="🧭 Сюжетное решение", callback_data="choice:open")],
    ]
)

TRAVEL_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🥾 Отправиться в путь", callback_data="travel:go")],
        [InlineKeyboardButton(text="📍 Текущее местоположение", callback_data="travel:where")],
        [InlineKeyboardButton(text="🧭 Случайное событие", callback_data="choice:open")],
    ]
)

REPUTATION_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить репутацию", callback_data="reputation:show")],
    ]
)

ACHIEVEMENTS_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить достижения", callback_data="achievements:show")],
    ]
)

DUNGEON_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🕯️ Начать экспедицию", callback_data="dungeon:start")],
        [InlineKeyboardButton(text="🥾 Продолжить путь", callback_data="dungeon:explore")],
        [InlineKeyboardButton(text="📍 Состояние экспедиции", callback_data="dungeon:status")],
        [InlineKeyboardButton(text="🏆 Подземные достижения", callback_data="dungeon:achievements")],
        [InlineKeyboardButton(text="🚪 Отступить", callback_data="dungeon:retreat")],
    ]
)

DUNGEON_ROOM_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🥾 Исследовать следующую комнату", callback_data="dungeon:explore")],
        [InlineKeyboardButton(text="📍 Состояние экспедиции", callback_data="dungeon:status")],
        [InlineKeyboardButton(text="🚪 Отступить с добычей", callback_data="dungeon:retreat")],
    ]
)

DUNGEON_BOSS_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🗡️ Атаковать босса", callback_data="dungeon:boss_attack")],
        [InlineKeyboardButton(text="📍 Оценить противника", callback_data="dungeon:status")],
        [InlineKeyboardButton(text="🚪 Бежать", callback_data="dungeon:retreat")],
    ]
)

SETTINGS_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🌿 Легко", callback_data="settings:difficulty:easy"),
            InlineKeyboardButton(text="⚔️ Обычно", callback_data="settings:difficulty:normal"),
            InlineKeyboardButton(text="💀 Хардкор", callback_data="settings:difficulty:hard"),
        ],
        [InlineKeyboardButton(text="🖼️ Фото · быстрее", callback_data="settings:image:photo")],
        [InlineKeyboardButton(text="💎 PNG · без сжатия", callback_data="settings:image:document")],
    ]
)

DICE_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="d4", callback_data="dice:d4"),
            InlineKeyboardButton(text="d6", callback_data="dice:d6"),
            InlineKeyboardButton(text="d8", callback_data="dice:d8"),
        ],
        [
            InlineKeyboardButton(text="d10", callback_data="dice:d10"),
            InlineKeyboardButton(text="d12", callback_data="dice:d12"),
            InlineKeyboardButton(text="d20", callback_data="dice:d20"),
        ],
        [
            InlineKeyboardButton(text="d100", callback_data="dice:d100"),
            InlineKeyboardButton(text="2d6", callback_data="dice:2d6"),
            InlineKeyboardButton(text="d20+3", callback_data="dice:d20+3"),
        ],
    ]
)

SPELL_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🔥 Огненный шар", callback_data="spell:Огненный шар"),
            InlineKeyboardButton(text="❄️ Ледяное копьё", callback_data="spell:Ледяное копьё"),
        ],
        [
            InlineKeyboardButton(text="⚡ Цепная молния", callback_data="spell:Цепная молния"),
            InlineKeyboardButton(text="🌑 Теневой луч", callback_data="spell:Теневой луч"),
        ],
        [InlineKeyboardButton(text="✍️ Назвать своё заклинание", callback_data="spell:custom")],
    ]
)

COMBAT_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Начать новый бой", callback_data="combat:start")],
        [
            InlineKeyboardButton(text="🗡️ Атаковать", callback_data="combat:attack"),
            InlineKeyboardButton(text="✨ Заклинание", callback_data="combat:spell"),
        ],
        [InlineKeyboardButton(text="🎯 Тактические действия", callback_data="v5:actions")],
        [InlineKeyboardButton(text="🛡️ Статус боя", callback_data="combat:status")],
    ]
)

COMBAT_ACTIONS_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🗡️ Обычная атака", callback_data="combat:attack")],
        [InlineKeyboardButton(text="💥 Рискованный удар", callback_data="v5:power:menu")],
        [InlineKeyboardButton(text="🛡️ Защитная стойка", callback_data="v5:guard")],
        [InlineKeyboardButton(text="✨ Заклинание", callback_data="combat:spell")],
        [InlineKeyboardButton(text="🤝 Лечение союзника", callback_data="support:show")],
        [InlineKeyboardButton(text="📊 Статус боя", callback_data="combat:status")],
    ]
)

MORE_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🧰 Снаряжение", callback_data="eq:show"),
            InlineKeyboardButton(text="🎰 Казино", callback_data="casino:status"),
        ],
        [InlineKeyboardButton(text="🧭 Сюжетное решение", callback_data="choice:open")],
        [InlineKeyboardButton(text="⬆️ Повышение уровня", callback_data="levelup:check")],
        [InlineKeyboardButton(text="📤 Экспорт журнала TXT", callback_data="journal:export")],
        [InlineKeyboardButton(text="❓ Как играть", callback_data="menu:help")],
    ]
)

JOURNAL_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить журнал", callback_data="journal:show")],
        [InlineKeyboardButton(text="📤 Экспортировать TXT", callback_data="journal:export")],
    ]
)

INVENTORY_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить инвентарь", callback_data="inventory:show")],
        [InlineKeyboardButton(text="🧰 Снаряжение героя", callback_data="eq:show")],
        [InlineKeyboardButton(text="🏪 Открыть лавку", callback_data="shop:show")],
    ]
)


def quest_list_keyboard(quests: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"📜 {quest['title']} ({quest['progress']}/{quest['target']})",
                callback_data=f"quest:view:{quest['id']}",
            )
        ]
        for quest in quests
    ]
    rows.append([InlineKeyboardButton(text="✨ Новый контракт", callback_data="quest:new")])
    rows.append([InlineKeyboardButton(text="🧭 Сюжетное решение", callback_data="choice:open")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quest_detail_keyboard(quest: dict[str, Any]) -> InlineKeyboardMarkup:
    quest_id = int(quest["id"])
    rows: list[list[InlineKeyboardButton]] = []
    if int(quest["progress"]) < int(quest["target"]):
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎯 Выполнить этап",
                    callback_data=f"quest:advance:{quest_id}",
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Завершить и получить награду",
                    callback_data=f"quest:complete:{quest_id}",
                )
            ]
        )
    rows.extend(
        [
            [InlineKeyboardButton(text="📚 К списку квестов", callback_data="quest:list")],
            [InlineKeyboardButton(text="🗑️ Отказаться", callback_data=f"quest:abandon:{quest_id}")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def attack_targets_keyboard(state: dict[str, Any]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for enemy in state.get("enemies", []):
        if enemy.get("alive", True) and enemy.get("hp", 0) > 0:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"🗡️ {enemy['id']}. {enemy['name']} ({enemy['hp']} HP)",
                        callback_data=f"attack:{enemy['id']}",
                    )
                ]
            )
    if state.get("party_mode"):
        rows.append(
            [
                InlineKeyboardButton(text="💥 Рискованный удар", callback_data="v5:power:menu"),
                InlineKeyboardButton(text="🛡️ Защита", callback_data="v5:guard"),
            ]
        )
        rows.append([InlineKeyboardButton(text="🎯 Все действия", callback_data="v5:actions")])
    rows.append([InlineKeyboardButton(text="📊 Статус боя", callback_data="combat:status")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def levelup_keyboard(character_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💪 Сила", callback_data=f"lvl:{character_id}:str"),
                InlineKeyboardButton(text="🏹 Ловкость", callback_data=f"lvl:{character_id}:dex"),
            ],
            [
                InlineKeyboardButton(text="🔮 Мудрость", callback_data=f"lvl:{character_id}:wis"),
                InlineKeyboardButton(text="❤️ Живучесть", callback_data=f"lvl:{character_id}:vit"),
            ],
        ]
    )


def inventory_keyboard(items: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    consumables = {"Зелье лечения": 0, "Большое зелье лечения": 1}
    for item in items:
        name = str(item["item_name"])
        if name in consumables and int(item["quantity"]) > 0:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"🧪 Использовать: {name}",
                        callback_data=f"inventory:use:{consumables[name]}",
                    )
                ]
            )
    rows.extend(
        [
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="inventory:show")],
            [InlineKeyboardButton(text="🧰 Снаряжение героя", callback_data="eq:show")],
            [InlineKeyboardButton(text="🏪 Открыть лавку", callback_data="shop:show")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_keyboard(items: tuple[dict[str, Any], ...]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"🛒 {item['name']} — {item['price']} зм.",
                callback_data=f"shop:buy:{index}",
            )
        ]
        for index, item in enumerate(items)
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="🧰 Снаряжение", callback_data="eq:show")],
            [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory:show")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
