from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.database import Database
from app.dice import ability_modifier
from app.dungeon_logic import (
    boss_retaliation,
    create_dungeon,
    difficulty_label,
    explore_next_room,
    player_attack_boss,
    victory_rewards,
)
from app.dungeon_store import DungeonStore
from app.gameplay import calculate_party_level
from app.session import SessionStore
from app.button_ui.common import esc, signed
from app.button_ui.keyboards import (
    BTN_DUNGEON,
    BTN_SETTINGS,
    CHARACTER_MENU,
    DUNGEON_BOSS_MENU,
    DUNGEON_MENU,
    DUNGEON_ROOM_MENU,
    MAIN_MENU,
    SETTINGS_MENU,
)
from app.button_ui.media import send_scene

ROOM_ICONS = {
    "lore": "📚",
    "trap": "⚠️",
    "treasure": "💎",
    "shrine": "✨",
    "encounter": "👁️",
    "boss": "🐉",
}
ROOM_SCENES = {
    "lore": "journal",
    "trap": "encounter_hostile",
    "treasure": "loot_rare",
    "shrine": "rest",
    "encounter": "encounter_neutral",
    "boss": "combat",
}


def build_dungeon_router(
    database: Database,
    session_store: SessionStore,
    dungeon_store: DungeonStore,
) -> Router:
    router = Router(name="button_dungeon")

    async def show_settings(message: Message) -> None:
        settings = await dungeon_store.get_settings(message.chat.id)
        image_label = "фото высокого качества" if settings["image_mode"] == "photo" else "оригинал без сжатия"
        await send_scene(
            message,
            "campaign",
            "🎛️ <b>Настройки кампании</b>\n\n"
            f"Сложность экспедиций: <b>{difficulty_label(settings['difficulty'])}</b>\n"
            f"Режим изображений: <b>{image_label}</b>\n\n"
            "Сцены автоматически подготавливаются в разрешении 1280×960. "
            "Режим документа полностью исключает дополнительное сжатие Telegram.",
            SETTINGS_MENU,
        )

    async def show_dungeon(message: Message) -> None:
        run = await dungeon_store.get_run(message.chat.id)
        if not run:
            settings = await dungeon_store.get_settings(message.chat.id)
            await send_scene(
                message,
                "campaign",
                "🏰 <b>Подземелье ждёт.</b>\n\n"
                f"Текущая сложность: <b>{difficulty_label(settings['difficulty'])}</b>. "
                "Начни экспедицию, исследуй комнаты и доберись до босса.",
                DUNGEON_MENU,
            )
            return

        boss = run.get("boss")
        boss_text = ""
        keyboard = DUNGEON_ROOM_MENU
        if boss and boss.get("alive", True):
            boss_text = (
                f"\n\n🐉 <b>{esc(boss['name'])}</b>\n"
                f"HP: {boss['hp']}/{boss['max_hp']} · КД {boss['ac']}"
            )
            keyboard = DUNGEON_BOSS_MENU
        await send_scene(
            message,
            "combat" if boss_text else "campaign",
            f"🏰 <b>{esc(run['name'])}</b>\n\n"
            f"Глубина: {run['depth']}/{run['max_depth']}\n"
            f"Сложность: {difficulty_label(run['difficulty'])}\n"
            f"Найдено в комнатах: {run.get('gold_earned', 0)} золотых"
            f"{boss_text}",
            keyboard,
        )

    async def begin_dungeon(message: Message) -> None:
        existing = await dungeon_store.get_run(message.chat.id)
        if existing:
            await send_scene(
                message,
                "campaign",
                f"🏰 Экспедиция <b>«{esc(existing['name'])}»</b> уже идёт.",
                DUNGEON_ROOM_MENU if not existing.get("boss") else DUNGEON_BOSS_MENU,
            )
            return
        character = await database.get_active_character(message.chat.id)
        if not character:
            await send_scene(
                message,
                "character",
                "🧙 <b>Для экспедиции нужен основной герой.</b>\n\nСоздай его в разделе «🧙 Герой».",
                CHARACTER_MENU,
            )
            return
        members = await database.get_party_members(message.chat.id)
        level = calculate_party_level(members, int(character.get("level", 1)))
        settings = await dungeon_store.get_settings(message.chat.id)
        run = create_dungeon(level, settings["difficulty"])
        await dungeon_store.start_run(message.chat.id, run)
        new_achievements = await dungeon_store.refresh_achievements(message.chat.id)
        achievement_text = ""
        if new_achievements:
            achievement_text = f"\n\n🏆 Открыто достижение: <b>{esc(new_achievements[0]['title'])}</b>"
        await session_store.log(
            message.chat.id,
            "dungeon",
            f"Начата экспедиция: {run['name']}, сложность {difficulty_label(run['difficulty'])}",
            payload=run,
        )
        await send_scene(
            message,
            "campaign",
            f"🕯️ <b>Экспедиция начинается</b>\n\n"
            f"Подземелье: <b>{esc(run['name'])}</b>\n"
            f"Глубина: {run['max_depth']} комнат\n"
            f"Уровень партии: {run['party_level']}\n"
            f"Сложность: {difficulty_label(run['difficulty'])}"
            f"{achievement_text}",
            DUNGEON_ROOM_MENU,
        )

    async def explore(message: Message) -> None:
        run = await dungeon_store.get_run(message.chat.id)
        if not run:
            await show_dungeon(message)
            return
        boss = run.get("boss")
        if boss and boss.get("alive", True):
            await send_scene(message, "combat", "🐉 Сначала одолей босса или отступи.", DUNGEON_BOSS_MENU)
            return

        character = await database.get_active_character(message.chat.id)
        try:
            room = explore_next_room(run)
        except ValueError as error:
            await send_scene(message, "campaign", f"⚠️ {esc(error)}", DUNGEON_MENU)
            return

        details: list[str] = []
        if int(room.get("gold", 0)) > 0:
            balance = await database.add_gold(message.chat.id, int(room["gold"]))
            details.append(f"💰 Найдено {room['gold']} золотых. Казна: {balance}.")
        if room.get("loot"):
            await database.add_inventory_item(message.chat.id, str(room["loot"]), "редкая", 1)
            details.append(f"🎒 В инвентарь добавлено: {esc(room['loot'])}.")
        if character and int(room.get("damage", 0)) > 0:
            character["current_hp"] = max(0, int(character["current_hp"]) - int(room["damage"]))
            await database.update_character(character)
            details.append(
                f"🩸 Ловушка наносит {room['damage']} урона. HP: {character['current_hp']}/{character['max_hp']}."
            )
        if character and int(room.get("healing", 0)) > 0:
            before = int(character["current_hp"])
            character["current_hp"] = min(int(character["max_hp"]), before + int(room["healing"]))
            restored = int(character["current_hp"]) - before
            await database.update_character(character)
            details.append(f"❤️ Восстановлено {restored} HP.")

        if character and int(character["current_hp"]) <= 0:
            await dungeon_store.save_run(message.chat.id, run, room_explored=True)
            await dungeon_store.finish_run(message.chat.id, run, "defeat")
            await session_store.log(message.chat.id, "dungeon", f"Экспедиция {run['name']} завершена поражением")
            await send_scene(
                message,
                "combat",
                f"☠️ <b>Экспедиция окончена</b>\n\n{esc(room['description'])}\n\nГерой пал в глубинах подземелья.",
                DUNGEON_MENU,
            )
            return

        await dungeon_store.save_run(message.chat.id, run, room_explored=True)
        await session_store.log(
            message.chat.id,
            "dungeon_room",
            f"Исследована комната {room['depth']}: {room['title']}",
            payload=room,
        )
        icon = ROOM_ICONS.get(str(room["type"]), "•")
        extra = "\n".join(details)
        if extra:
            extra = "\n\n" + extra
        keyboard = DUNGEON_BOSS_MENU if room["type"] == "boss" else DUNGEON_ROOM_MENU
        await send_scene(
            message,
            ROOM_SCENES.get(str(room["type"]), "campaign"),
            f"{icon} <b>{esc(room['title'])}</b>\n\n"
            f"Комната {room['depth']}/{run['max_depth']}\n\n"
            f"{esc(room['description'])}{extra}",
            keyboard,
        )

    async def attack_boss(message: Message) -> None:
        run = await dungeon_store.get_run(message.chat.id)
        if not run or not run.get("boss"):
            await show_dungeon(message)
            return
        character = await database.get_active_character(message.chat.id)
        if not character:
            await send_scene(message, "character", "🧙 Основной герой не найден.", CHARACTER_MENU)
            return

        strength_mod = ability_modifier(int(character["abilities"]["СИЛ"]))
        dex_mod = ability_modifier(int(character["abilities"]["ЛОВ"]))
        level = max(1, int(character.get("level", 1)))
        proficiency = 2 + max(0, (level - 1) // 4)
        attack_result = player_attack_boss(run, strength_mod + proficiency, strength_mod)
        boss = attack_result["boss"]

        if attack_result["critical"]:
            outcome = f"💥 Критический удар: <b>{attack_result['damage']} урона</b>."
        elif attack_result["hit"]:
            outcome = f"🗡️ Попадание: <b>{attack_result['damage']} урона</b>."
        else:
            outcome = "🛡️ Босс отражает атаку."
        text = (
            f"🐉 <b>{esc(boss['name'])}</b>\n\n"
            f"🎲 {attack_result['natural']} {signed(strength_mod + proficiency)} = "
            f"<b>{attack_result['total']}</b> против КД {boss['ac']}\n"
            f"{outcome}\n"
            f"HP босса: {boss['hp']}/{boss['max_hp']}"
        )

        if attack_result["defeated"]:
            rewards = victory_rewards(run)
            balance = await database.add_gold(message.chat.id, int(rewards["gold"]))
            await database.add_inventory_item(message.chat.id, str(rewards["loot"]), "легендарная", 1)
            character["xp"] = int(character.get("xp", 0)) + int(rewards["xp"])
            await database.update_character(character)
            achievements = await dungeon_store.finish_run(
                message.chat.id, run, "victory", int(rewards["gold"])
            )
            achievement_text = ""
            if achievements:
                achievement_text = "\n\n" + "\n".join(
                    f"🏆 <b>{esc(item['title'])}</b> — {esc(item['description'])}" for item in achievements
                )
            await session_store.log(
                message.chat.id,
                "dungeon_victory",
                f"Побеждён {boss['name']}; получено {rewards['gold']} золота и {rewards['loot']}",
            )
            await send_scene(
                message,
                "levelup",
                text
                + "\n\n🏆 <b>Босс повержен!</b>"
                + f"\n💰 Награда: {rewards['gold']} золотых (казна: {balance})"
                + f"\n✨ Опыт: {rewards['xp']} XP"
                + f"\n🎒 Легендарная добыча: {esc(rewards['loot'])}"
                + achievement_text,
                DUNGEON_MENU,
            )
            return

        retaliation = boss_retaliation(run, 10 + dex_mod)
        if retaliation["critical"]:
            response = f"💥 Босс отвечает критом и наносит {retaliation['damage']} урона."
        elif retaliation["hit"]:
            response = f"🩸 Ответный удар босса: {retaliation['damage']} урона."
        else:
            response = "🌫️ Ответная атака босса проходит мимо."
        character["current_hp"] = max(0, int(character["current_hp"]) - int(retaliation["damage"]))
        await database.update_character(character)
        text += f"\n\n{response}\n❤️ HP героя: {character['current_hp']}/{character['max_hp']}"

        if int(character["current_hp"]) <= 0:
            await dungeon_store.finish_run(message.chat.id, run, "defeat")
            text += "\n\n☠️ <b>Герой пал. Экспедиция завершена поражением.</b>"
            keyboard = DUNGEON_MENU
        else:
            await dungeon_store.save_run(message.chat.id, run)
            keyboard = DUNGEON_BOSS_MENU
        await send_scene(message, "combat", text, keyboard)

    async def retreat(message: Message) -> None:
        run = await dungeon_store.get_run(message.chat.id)
        if not run:
            await send_scene(message, "campaign", "🚪 Активной экспедиции нет.", DUNGEON_MENU)
            return
        achievements = await dungeon_store.finish_run(message.chat.id, run, "retreat")
        achievement_text = ""
        if achievements:
            achievement_text = f"\n\n🏆 Открыто: <b>{esc(achievements[0]['title'])}</b>"
        await session_store.log(message.chat.id, "dungeon", f"Партия отступила из {run['name']}")
        await send_scene(
            message,
            "rest",
            f"🚪 <b>Партия отступает</b>\n\n"
            f"Исследовано комнат: {run['depth']}/{run['max_depth']}. "
            "Уже найденные предметы и золото сохранены."
            f"{achievement_text}",
            DUNGEON_MENU,
        )

    async def show_achievements(message: Message) -> None:
        achievements = await dungeon_store.list_achievements(message.chat.id)
        stats = await dungeon_store.get_stats(message.chat.id)
        body = "Пока ни одного достижения." if not achievements else "\n\n".join(
            f"🏆 <b>{esc(item['title'])}</b>\n{esc(item['description'])}" for item in achievements
        )
        await send_scene(
            message,
            "levelup",
            "🏰 <b>Летопись подземелий</b>\n\n"
            f"Экспедиций: {stats['runs_started']}\n"
            f"Комнат исследовано: {stats['rooms_explored']}\n"
            f"Боссов побеждено: {stats['bosses_defeated']}\n"
            f"Отступлений: {stats['retreats']}\n\n{body}",
            DUNGEON_MENU,
        )

    @router.message(F.text == BTN_DUNGEON)
    async def dungeon_button(message: Message) -> None:
        await show_dungeon(message)

    @router.message(F.text == BTN_SETTINGS)
    async def settings_button(message: Message) -> None:
        await show_settings(message)

    @router.callback_query(F.data == "dungeon:start")
    async def dungeon_start(callback: CallbackQuery) -> None:
        await callback.answer()
        await begin_dungeon(callback.message)

    @router.callback_query(F.data == "dungeon:explore")
    async def dungeon_explore(callback: CallbackQuery) -> None:
        await callback.answer("Исследуем глубины…")
        await explore(callback.message)

    @router.callback_query(F.data == "dungeon:status")
    async def dungeon_status(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_dungeon(callback.message)

    @router.callback_query(F.data == "dungeon:boss_attack")
    async def dungeon_boss_attack(callback: CallbackQuery) -> None:
        await callback.answer("Атака!")
        await attack_boss(callback.message)

    @router.callback_query(F.data == "dungeon:retreat")
    async def dungeon_retreat(callback: CallbackQuery) -> None:
        await callback.answer()
        await retreat(callback.message)

    @router.callback_query(F.data == "dungeon:achievements")
    async def dungeon_achievements(callback: CallbackQuery) -> None:
        await callback.answer()
        await show_achievements(callback.message)

    @router.callback_query(F.data.startswith("settings:difficulty:"))
    async def set_difficulty(callback: CallbackQuery) -> None:
        value = callback.data.rsplit(":", 1)[1]
        await dungeon_store.set_difficulty(callback.message.chat.id, value)
        await callback.answer("Сложность сохранена")
        await show_settings(callback.message)

    @router.callback_query(F.data.startswith("settings:image:"))
    async def set_image_mode(callback: CallbackQuery) -> None:
        value = callback.data.rsplit(":", 1)[1]
        await dungeon_store.set_image_mode(callback.message.chat.id, value)
        await callback.answer("Режим изображения сохранён")
        await show_settings(callback.message)

    return router
