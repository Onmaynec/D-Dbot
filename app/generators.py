from __future__ import annotations

import random
from typing import Any

from app.dice import ability_modifier

NAMES = [
    "Аэлин Тихий Шаг", "Бром Камнещит", "Сайра Ночная Искра", "Торвен Серый Ворон",
    "Лиора Звёздная Пыль", "Гаррик Медный Клык", "Ним Ветролов", "Элиан Чернильный Маг",
    "Руна Ледяная Кровь", "Касс Вольный Клинок", "Мира Туманная", "Орен Последний Фонарь",
]
RACES = ["человек", "эльф", "дворф", "полурослик", "тифлинг", "драконорождённый", "полуорк", "гном"]
CLASSES = ["воин", "плут", "волшебник", "жрец", "следопыт", "варвар", "бард", "колдун", "паладин", "друид"]
BACKGROUNDS = ["изгнанник", "учёный", "солдат", "шарлатан", "народный герой", "моряк", "отшельник", "ремесленник"]
CLASS_HIT_DIE = {
    "варвар": 12, "воин": 10, "паладин": 10, "следопыт": 10,
    "бард": 8, "жрец": 8, "друид": 8, "плут": 8, "колдун": 8, "волшебник": 6,
}

WORLD_TYPES = ["классическое фэнтези", "мрачное фэнтези", "sci-fi", "космический хоррор", "готический хоррор"]
WORLD_PREFIXES = ["Эхо", "Хроники", "Тени", "Предел", "Песнь", "Пепел", "Ковчег", "Зов"]
WORLD_SUFFIXES = ["Семи Лун", "Багровой Кометы", "Расколотого Трона", "Бездонного Моря", "Стеклянных Звёзд", "Спящего Бога"]
FACTIONS = [
    "Орден Латунного Рассвета", "Синдикат Чёрной Розы", "Хранители Безмолвной Башни",
    "Конклав Звёздных Картографов", "Культ Последнего Колокола", "Лига Вольных Городов",
    "Дом Серебряного Змея", "Экспедиционный корпус «Гелиос»", "Дети Пепельной Луны",
]

QUEST_GIVERS = ["усталый трактирщик", "наследница разорённого дома", "говорящий ворон", "раненый капитан", "архивариус запретной библиотеки", "посол в маске"]
QUEST_GOALS = [
    "найти пропавший караван", "украсть карту из неприступного архива", "закрыть портал под старым храмом",
    "сопроводить свидетеля через вражескую территорию", "вернуть реликвию до наступления затмения",
    "выяснить, почему жители деревни перестали видеть сны",
]
QUEST_REWARDS = ["мешок древних монет", "редкий магический предмет", "право на землю", "секретный проход в столицу", "покровительство влиятельной фракции", "500 золотых и одна услуга"]
QUEST_COMPLICATIONS = [
    "заказчик скрывает истинную цель", "цель уже перешла на сторону врага", "время ограничено одной ночью",
    "соперничающая группа идёт по следу", "награда проклята", "виновник — союзник героев",
]

APPEARANCES = [
    "высокая фигура в плаще, расшитом созвездиями", "невысокий ветеран с серебряным протезом руки",
    "бледная женщина с глазами цвета янтаря", "улыбчивый торговец с татуировками-картами",
    "молчаливый подросток, за которым летят бумажные мотыльки", "старик в безупречно чистой дорожной броне",
]
TRAITS = ["говорит загадками", "не терпит лжи", "слишком любопытен", "вежлив даже в ярости", "смеётся в опасные моменты", "всё записывает"]
SECRETS = [
    "служит одной из враждующих фракций", "на самом деле является перевёртышем", "видел будущее одного из героев",
    "хранит ключ от запретного хранилища", "виновен в недавней катастрофе", "пытается разрушить собственное пророчество",
]
ATTITUDES = ["настороженно-доброжелательное", "почтительное", "холодное", "заинтересованное", "скрыто враждебное", "восхищённое"]

ENCOUNTER_KINDS = {
    "дружелюбная": [
        "Путевой лекарь предлагает помощь и просит лишь рассказать правдивую историю.",
        "Караван артистов зовёт героев к костру и делится слухами о ближайшем городе.",
        "Маленький дух дороги возвращает потерянную вещь и просит дать ему имя.",
    ],
    "нейтральная": [
        "На перекрёстке стоит дверь без стены; из-за неё слышен шум чужого праздника.",
        "Отряд другой фракции молча проводит раскопки и не желает объяснять находку.",
        "Над дорогой зависло неподвижное облако, отбрасывающее тень в форме дракона.",
    ],
    "враждебная": [
        "Разбойники перекрывают путь, но их предводитель явно боится того, что скрывается позади.",
        "Стая искажённых зверей выходит из тумана, реагируя на любой громкий звук.",
        "Охотник за головами называет имя одного из героев и обнажает клинок.",
    ],
}

LOOT_BY_RARITY = {
    "обычная": ["набор серебряных столовых приборов", "мешочек с 24 золотыми", "добротный дорожный плащ", "карта местных троп"],
    "редкая": ["кольцо дыхания под водой", "клинок, светящийся рядом с ложью", "плащ бесшумных шагов", "эликсир каменной кожи"],
    "эпическая": ["компас, указывающий на сильнейшее желание владельца", "доспех из чешуи сумеречного дракона", "посох запечатанной бури", "маска тысячи лиц"],
    "легендарная": ["Корона Погасшего Солнца", "меч «Последнее Слово»", "Сердце Звёздного Титана", "Книга Неслучившихся Судеб"],
}

REST_EVENTS = [
    "Ночь проходит спокойно, но на рассвете вокруг лагеря находят круг свежих следов.",
    "Во сне каждый герой слышит один и тот же далёкий колокол.",
    "К костру выходит путник, называющий себя другом из будущего.",
    "С неба падает холодная звезда и гаснет неподалёку.",
    "Дежурный замечает, что одна из теней движется отдельно от хозяина.",
    "Ничего не происходит. Именно это и кажется самым тревожным.",
]


def _rng(rng: random.Random | None) -> random.Random:
    return rng or random  # type: ignore[return-value]


def _ability_score(rng: random.Random) -> int:
    rolls = sorted(rng.randint(1, 6) for _ in range(4))
    return sum(rolls[1:])


def generate_character(rng: random.Random | None = None) -> dict[str, Any]:
    roller = _rng(rng)
    character_class = roller.choice(CLASSES)
    abilities = {
        "СИЛ": _ability_score(roller), "ЛОВ": _ability_score(roller), "ТЕЛ": _ability_score(roller),
        "ИНТ": _ability_score(roller), "МДР": _ability_score(roller), "ХАР": _ability_score(roller),
    }
    max_hp = max(1, CLASS_HIT_DIE[character_class] + ability_modifier(abilities["ТЕЛ"]))
    return {
        "name": roller.choice(NAMES),
        "race": roller.choice(RACES),
        "class": character_class,
        "background": roller.choice(BACKGROUNDS),
        "abilities": abilities,
        "level": 1,
        "xp": 0,
        "max_hp": max_hp,
        "current_hp": max_hp,
    }


def generate_campaign(title: str | None = None, rng: random.Random | None = None) -> dict[str, Any]:
    roller = _rng(rng)
    world_name = f"{roller.choice(WORLD_PREFIXES)} {roller.choice(WORLD_SUFFIXES)}"
    return {
        "name": title.strip() if title and title.strip() else world_name,
        "world_name": world_name,
        "world_type": roller.choice(WORLD_TYPES),
        "factions": roller.sample(FACTIONS, 3),
    }


def generate_quest(campaign_name: str | None = None, rng: random.Random | None = None) -> dict[str, str]:
    roller = _rng(rng)
    return {
        "giver": roller.choice(QUEST_GIVERS),
        "goal": roller.choice(QUEST_GOALS),
        "reward": roller.choice(QUEST_REWARDS),
        "complication": roller.choice(QUEST_COMPLICATIONS),
        "campaign": campaign_name or "безымянные земли",
    }


def generate_npc(campaign_name: str | None = None, rng: random.Random | None = None) -> dict[str, str]:
    roller = _rng(rng)
    return {
        "name": roller.choice(NAMES),
        "appearance": roller.choice(APPEARANCES),
        "trait": roller.choice(TRAITS),
        "secret": roller.choice(SECRETS),
        "attitude": roller.choice(ATTITUDES),
        "campaign": campaign_name or "безымянные земли",
    }


def generate_encounter(campaign_name: str | None = None, rng: random.Random | None = None) -> dict[str, str]:
    roller = _rng(rng)
    kind = roller.choices(["дружелюбная", "нейтральная", "враждебная"], weights=[30, 35, 35], k=1)[0]
    return {
        "kind": kind,
        "description": roller.choice(ENCOUNTER_KINDS[kind]),
        "campaign": campaign_name or "безымянные земли",
    }


def generate_loot(campaign_name: str | None = None, rng: random.Random | None = None) -> dict[str, str]:
    roller = _rng(rng)
    rarity = roller.choices(["обычная", "редкая", "эпическая", "легендарная"], weights=[60, 27, 10, 3], k=1)[0]
    return {
        "rarity": rarity,
        "item": roller.choice(LOOT_BY_RARITY[rarity]),
        "campaign": campaign_name or "безымянные земли",
    }


def generate_rest_event(rng: random.Random | None = None) -> str:
    return _rng(rng).choice(REST_EVENTS)


def generate_spell(spell_name: str, rng: random.Random | None = None) -> dict[str, Any]:
    roller = _rng(rng)
    schools = ["воплощение", "иллюзия", "некромантия", "прорицание", "очарование", "преобразование"]
    visuals = [
        "руны вспыхивают синим пламенем", "пространство покрывается тонкими трещинами",
        "из воздуха вырываются серебряные нити", "тени собираются в крылатый силуэт",
        "время на миг замедляется", "над целью раскрывается мерцающее око",
    ]
    return {
        "name": spell_name.strip().title(),
        "school": roller.choice(schools),
        "visual": roller.choice(visuals),
        "save": roller.choice(["бросок атаки заклинанием", "спасбросок Ловкости", "спасбросок Мудрости"]),
        "damage_die": roller.choice([6, 8, 10, 12]),
    }
