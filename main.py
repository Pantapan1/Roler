import asyncio
import sqlite3
import random
import os
import re

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from aiogram.types import FSInputFile

TOKEN = "8656185873:AAEuggUpzeDNDZv4jtX7OkzFyey0KTLH1Tg"
ADMIN_ID = 6241704486

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

gm_active_npc = {}
combat_queue = []
current_turn_index = 0
combat_active = False

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="create", description="📝 Создать персонажа"),
        BotCommand(command="join", description="⚔️ Войти в игру"),
        BotCommand(command="spectate", description="👁 Войти как зритель"),
        BotCommand(command="me", description="👤 Профиль и Инвентарь"),
        BotCommand(command="market", description="🛒 Рынок"),
        BotCommand(command="use", description="🧪 Использовать"),
        BotCommand(command="equip", description="🛡 Экипировать"),
        BotCommand(command="lore", description="📚 Вики/Лор"),
        BotCommand(command="quest", description="🎯 Текущая цель"),
        BotCommand(command="roll", description="🎲 Бросить кубик"),
        BotCommand(command="help", description="❓ Помощь")
    ]
    await bot.set_my_commands(commands)

def init_db():
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, character_name TEXT, bio TEXT, hp INTEGER, xp INTEGER, is_gm BOOLEAN, gold INTEGER DEFAULT 0, strength INTEGER DEFAULT 0, agility INTEGER DEFAULT 0, intelligence INTEGER DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS session_players (user_id INTEGER PRIMARY KEY, status TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS session_monsters (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, hp INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, quantity INTEGER, is_equipped BOOLEAN DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, message TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS global_state (key TEXT PRIMARY KEY, value TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS lore (topic TEXT PRIMARY KEY, description TEXT, media_id TEXT, media_type TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS market (id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT, price INTEGER, description TEXT)')
    
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [col[1] for col in cursor.fetchall()]
    if 'gold' not in user_cols: cursor.execute("ALTER TABLE users ADD COLUMN gold INTEGER DEFAULT 0")
    if 'strength' not in user_cols: cursor.execute("ALTER TABLE users ADD COLUMN strength INTEGER DEFAULT 0")
    if 'agility' not in user_cols: cursor.execute("ALTER TABLE users ADD COLUMN agility INTEGER DEFAULT 0")
    if 'intelligence' not in user_cols: cursor.execute("ALTER TABLE users ADD COLUMN intelligence INTEGER DEFAULT 0")

    cursor.execute("PRAGMA table_info(lore)")
    lore_cols = [col[1] for col in cursor.fetchall()]
    if 'media_id' not in lore_cols: cursor.execute("ALTER TABLE lore ADD COLUMN media_id TEXT")
    if 'media_type' not in lore_cols: cursor.execute("ALTER TABLE lore ADD COLUMN media_type TEXT")

    cursor.execute("PRAGMA table_info(inventory)")
    inv_cols = [col[1] for col in cursor.fetchall()]
    if 'is_equipped' not in inv_cols: cursor.execute("ALTER TABLE inventory ADD COLUMN is_equipped BOOLEAN DEFAULT 0")

    cursor.execute("INSERT OR IGNORE INTO global_state (key, value) VALUES ('current_quest', 'Свободное исследование мира')")
    conn.commit()
    conn.close()

def get_character(user_id):
    conn = sqlite3.connect('rp_database.db')
    res = conn.execute("SELECT character_name FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return res[0] if res else None

def get_all_session_users():
    conn = sqlite3.connect('rp_database.db')
    res = [row[0] for row in conn.execute("SELECT user_id FROM session_players").fetchall()]
    conn.close()
    return res

def get_active_players():
    conn = sqlite3.connect('rp_database.db')
    res = [row[0] for row in conn.execute("SELECT user_id FROM session_players WHERE status = 'player'").fetchall()]
    conn.close()
    return res

def log_message_to_db(sender, text):
    conn = sqlite3.connect('rp_database.db')
    conn.execute("INSERT INTO logs (sender, message) VALUES (?, ?)", (sender, text))
    conn.commit()
    conn.close()

class RPState(StatesGroup):
    register_name = State()
    register_bio = State()
    in_session = State()

class GMAction(StatesGroup):
    target_id = State()
    target_type = State()
    action_type = State()
    waiting_for_value = State()
    waiting_for_broadcast = State()

class GMLore(StatesGroup):
    topic = State()
    content = State()

@dp.message(Command("cancel"))
async def cancel_any_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🛑 Действие отменено.")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📜 <b>СПРАВОЧНИК ИГРОКА</b>\n\n"
        "🔹 /create — Создать персонажа\n"
        "🔹 /join | /spectate — Войти как Игрок / Зритель\n"
        "🔹 /me — Профиль, Статы, Золото и Инвентарь\n"
        "🔹 <code>/use [Название]</code> — Использовать предмет\n"
        "🔹 <code>/equip [Название]</code> — Надеть/снять предмет\n"
        "🔹 /market — Открыть рынок (Купить: <code>/buy [ID]</code>)\n"
        "🔹 /lore — Открыть Вики по миру\n"
        "🔹 /quest — Посмотреть текущее задание\n"
        "🔹 <code>/w [Имя] [Текст]</code> — Шепот игроку\n"
        "🔹 /roll — Бросок d20. (Можно <code>/roll str</code>, <code>/roll agi</code>, <code>/roll int</code>)\n\n"
        "💡 <b>ОТЫГРЫШ:</b>\n"
        "<code>*действия*</code>, <code>(мысли)</code>, <code>\"прямая речь\"</code>.\n\n"
    )
    if message.from_user.id == ADMIN_ID:
        text += (
            "🛠 <b>КОМАНДЫ ГМа</b>\n\n"
            "🔸 /open_session | /archive — Управление сессией\n"
            "🔸 /panel — Выдать урон, ХП, лут, золото\n"
            "🔸 /broadcast — Глобальная рассылка\n"
            "🔸 /spawn [ХП] [Имя] — Создать монстра\n"
            "🔸 <b>БОЙ:</b> /combat_start, /next_turn, /combat_end\n"
            "🔸 <b>РЫНОК:</b> <code>/add_market [Цена] [Название] - [Описание]</code>, <code>/del_market [ID]</code>\n"
            "🔸 <b>СТАТЫ:</b> <code>/set_stats [ID] [STR] [AGI] [INT]</code>\n"
            "🔸 <code>/set_quest</code>, <code>/env</code>, <code>/event</code>, <code>/npc</code>, <code>/as_npc</code>\n"
        )
    await message.answer(text)

@dp.message(Command("start", "create"))
async def cmd_create_char(message: types.Message, state: FSMContext):
    await message.answer("📝 Введи <b>Имя</b> своего героя:")
    await state.set_state(RPState.register_name)

@dp.message(RPState.register_name, F.text)
async def register_name(message: types.Message, state: FSMContext):
    await state.update_data(char_name=message.text)
    await message.answer(f"Имя: <b>{message.text}</b>!\nТеперь опиши свой <b>Класс и биографию</b>:")
    await state.set_state(RPState.register_bio)

@dp.message(RPState.register_bio, F.text)
async def register_bio(message: types.Message, state: FSMContext):
    data = await state.get_data()
    char_name = data.get("char_name")
    bio = message.text
    user_id = message.from_user.id
    conn = sqlite3.connect('rp_database.db')
    conn.execute(
        "INSERT OR REPLACE INTO users (user_id, character_name, bio, hp, xp, is_gm, gold, strength, agility, intelligence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, char_name, bio, 100, 0, user_id == ADMIN_ID, 0, 0, 0, 0)
    )
    conn.commit()
    conn.close()
    await message.answer(f"✅ Персонаж <b>{char_name}</b> успешно создан!")
    await state.clear()

@dp.message(Command("join"))
async def join_session(message: types.Message, state: FSMContext):
    char_name = get_character(message.from_user.id)
    if not char_name: return await message.answer("Сначала создай персонажа через /create")
    conn = sqlite3.connect('rp_database.db')
    conn.execute("INSERT OR REPLACE INTO session_players (user_id, status) VALUES (?, ?)", (message.from_user.id, 'player'))
    conn.commit()
    conn.close()
    await state.set_state(RPState.in_session)
    for pid in get_all_session_users():
        if pid != message.from_user.id:
            await bot.send_message(pid, f"<i>👤 {char_name} присоединяется к игре.</i>")
    await message.answer(f"✅ Ты вошел в игру как <b>{char_name}</b>.")

@dp.message(Command("spectate"))
async def spectate_session(message: types.Message):
    conn = sqlite3.connect('rp_database.db')
    conn.execute("INSERT OR REPLACE INTO session_players (user_id, status) VALUES (?, ?)", (message.from_user.id, 'spectator'))
    conn.commit()
    conn.close()
    await message.answer("👁 Ты подключился к сессии как зритель.")

@dp.message(Command("open_session"))
async def open_session(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('rp_database.db')
    conn.execute("DELETE FROM session_players") 
    conn.execute("DELETE FROM session_monsters") 
    conn.execute("DELETE FROM logs")            
    all_users = [row[0] for row in conn.execute("SELECT user_id FROM users").fetchall()]
    conn.commit()
    conn.close()
    await message.answer("🌍 Глобальная РП сессия открыта! Начинаю рассылку...")
    success = 0
    for uid in all_users:
        if uid != ADMIN_ID:
            try:
                await bot.send_message(uid, "📢 <b>ГМ открыл набор на сессию!</b>\nПиши /join чтобы войти в игру.")
                success += 1
                await asyncio.sleep(0.05)
            except: pass
    await message.answer(f"✅ Уведомления разосланы ({success} чел.).")

@dp.message(Command("archive", "close_session"))
async def archive_and_close_session(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('rp_database.db')
    logs = conn.execute("SELECT sender, message FROM logs").fetchall()
    if not logs: return await message.answer("Лог пуст.")
    archive_content = "=== ХРОНИКИ СЕССИИ RL™ ===\n\n"
    for sender, text in logs: archive_content += f"[{sender}]: {text}\n"
    filename = "RL_Session_Archive.txt"
    with open(filename, "w", encoding="utf-8") as file: file.write(archive_content)
    for pid in get_all_session_users():
        try:
            await bot.send_message(pid, "🛑 <b>СЕССИЯ ЗАВЕРШЕНА!</b>\nСюжет сохранен в архив.")
            await bot.send_document(pid, FSInputFile(filename))
        except: pass
    conn.execute("DELETE FROM session_players")
    conn.execute("DELETE FROM session_monsters")
    conn.commit()
    conn.close()
    await state.clear()
    os.remove(filename)
    await message.answer("✅ Архив отправлен. Сессия закрыта.")

@dp.message(Command("me"))
async def check_stats(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect('rp_database.db')
    user_data = conn.execute("SELECT character_name, bio, hp, xp, gold, strength, agility, intelligence FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user_data: return await message.answer("Сначала создай персонажа через /create")
    name, bio, hp, xp, gold, str_stat, agi_stat, int_stat = user_data
    items = conn.execute("SELECT item_name, quantity, is_equipped FROM inventory WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    inv_list = []
    for item_name, qty, is_eq in items:
        prefix = "⚔️ [НАДЕТО] " if is_eq else "🔹 "
        inv_list.append(f"{prefix}{item_name} (x{qty})")
    inv_text = "\n".join(inv_list) if inv_list else "Пусто"
    text = (
        f"👤 <b>Персонаж:</b> {name}\n"
        f"📜 <b>Био:</b> {bio}\n"
        f"❤️ <b>ХП:</b> {hp} | ✨ <b>Опыт:</b> {xp} | 🪙 <b>Золото:</b> {gold}\n\n"
        f"🧬 <b>Характеристики:</b>\n"
        f"💪 Сила: {str_stat} | 🏃 Ловкость: {agi_stat} | 🧠 Интеллект: {int_stat}\n\n"
        f"🎒 <b>Инвентарь:</b>\n{inv_text}"
    )
    await message.answer(text)

@dp.message(Command("set_stats"))
async def set_player_stats(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    args = command.args.split() if command.args else []
    if len(args) != 4: return await message.answer("Формат: /set_stats [ID] [STR] [AGI] [INT]")
    try:
        uid, s, a, i = map(int, args)
        conn = sqlite3.connect('rp_database.db')
        conn.execute("UPDATE users SET strength=?, agility=?, intelligence=? WHERE user_id=?", (s, a, i, uid))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Статы обновлены для ID {uid}.")
    except Exception:
        await message.answer("Ошибка ввода.")

@dp.message(Command("quest"))
async def check_quest(message: types.Message):
    conn = sqlite3.connect('rp_database.db')
    quest = conn.execute("SELECT value FROM global_state WHERE key = 'current_quest'").fetchone()
    conn.close()
    await message.answer(f"🎯 <b>ТЕКУЩАЯ ЦЕЛЬ:</b>\n{quest[0] if quest else 'Нет заданий.'}")

@dp.message(Command("set_quest"))
async def set_quest(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID or not command.args: return
    conn = sqlite3.connect('rp_database.db')
    conn.execute("UPDATE global_state SET value = ? WHERE key = 'current_quest'", (command.args,))
    conn.commit()
    conn.close()
    for pid in get_all_session_users(): await bot.send_message(pid, f"📜 <b>ОБНОВЛЕНИЕ ЗАДАНИЯ:</b>\n{command.args}")

@dp.message(Command("use"))
async def use_item(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /use [Название]")
    item_name = command.args.strip()
    user_id = message.from_user.id
    char_name = get_character(user_id)
    if not char_name: return await message.answer("Создай персонажа!")
    conn = sqlite3.connect('rp_database.db')
    item = conn.execute("SELECT id, quantity FROM inventory WHERE user_id = ? AND item_name LIKE ?", (user_id, f"{item_name}%")).fetchone()
    if not item:
        conn.close()
        return await message.answer("❌ У тебя нет такого предмета.")
    item_id, qty = item
    if qty > 1: conn.execute("UPDATE inventory SET quantity = quantity - 1 WHERE id = ?", (item_id,))
    else: conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    broadcast_msg = f"🧪 <b>{char_name}</b> использует предмет: <b>{item_name}</b>!"
    users = get_all_session_users()
    if not users: users = [user_id]
    for pid in users: await bot.send_message(pid, broadcast_msg)
    log_message_to_db("СИСТЕМА", broadcast_msg)

@dp.message(Command("equip"))
async def equip_item(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /equip [Название]")
    item_name = command.args.strip()
    user_id = message.from_user.id
    char_name = get_character(user_id)
    if not char_name: return await message.answer("Создай персонажа!")
    conn = sqlite3.connect('rp_database.db')
    item = conn.execute("SELECT id, is_equipped, item_name FROM inventory WHERE user_id = ? AND item_name LIKE ?", (user_id, f"{item_name}%")).fetchone()
    if not item:
        conn.close()
        return await message.answer("❌ Такого предмета нет в рюкзаке.")
    item_id, is_equipped, full_item_name = item
    new_status = 0 if is_equipped else 1
    conn.execute("UPDATE inventory SET is_equipped = ? WHERE id = ?", (new_status, item_id))
    conn.commit()
    conn.close()
    action = "снимает" if is_equipped else "экипирует"
    icon = "🎒" if is_equipped else "⚔️"
    broadcast_msg = f"{icon} <b>{char_name}</b> {action} предмет: <b>{full_item_name}</b>!"
    users = get_all_session_users()
    if not users: users = [user_id]
    for pid in users: await bot.send_message(pid, broadcast_msg)
    log_message_to_db("СИСТЕМА", broadcast_msg)

@dp.message(Command("market"))
async def market_view(message: types.Message):
    conn = sqlite3.connect('rp_database.db')
    items = conn.execute("SELECT id, item_name, price, description FROM market").fetchall()
    conn.close()
    if not items: return await message.answer("🛒 <b>Рынок пуст.</b>")
    text = "🛒 <b>МЕСТНЫЙ ТОРГОВЕЦ ПРЕДЛАГАЕТ:</b>\n\n"
    for item_id, name, price, desc in items:
        text += f"📦 [ID: <b>{item_id}</b>] <b>{name}</b> — 🪙 {price} золота\n<i>{desc}</i>\n\n"
    text += "🛒 Чтобы купить, напиши: <code>/buy [ID]</code>"
    await message.answer(text)

@dp.message(Command("add_market"))
async def add_to_market(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("Формат: /add_market [Цена] [Название] - [Описание]")
    try:
        price_str, rest = command.args.split(maxsplit=1)
        price = int(price_str)
        name, desc = rest.split("-", 1)
        name, desc = name.strip(), desc.strip()
        conn = sqlite3.connect('rp_database.db')
        conn.execute("INSERT INTO market (item_name, price, description) VALUES (?, ?, ?)", (name, price, desc))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Товар <b>{name}</b> за {price} золота добавлен!")
    except Exception:
        await message.answer("Ошибка формата.")

@dp.message(Command("del_market"))
async def del_from_market(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args or not command.args.isdigit(): return await message.answer("Укажи ID: /del_market [ID]")
    conn = sqlite3.connect('rp_database.db')
    conn.execute("DELETE FROM market WHERE id = ?", (int(command.args),))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Товар с ID {command.args} удален.")

@dp.message(Command("buy"))
async def buy_item(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit(): return await message.answer("Как купить: /buy [ID товара]")
    item_id = int(command.args)
    user_id = message.from_user.id
    char_name = get_character(user_id)
    if not char_name: return await message.answer("Создай персонажа!")
    conn = sqlite3.connect('rp_database.db')
    item = conn.execute("SELECT item_name, price FROM market WHERE id = ?", (item_id,)).fetchone()
    if not item:
        conn.close()
        return await message.answer("❌ Такого товара нет.")
    item_name, price = item
    current_gold = conn.execute("SELECT gold FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]
    if current_gold < price:
        conn.close()
        return await message.answer(f"❌ Недостаточно золота. Нужно {price}, есть {current_gold}.")
    conn.execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (price, user_id))
    inv_item = conn.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name)).fetchone()
    if inv_item: conn.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_name = ?", (user_id, item_name))
    else: conn.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (user_id, item_name))
    conn.commit()
    conn.close()
    success_msg = f"🛍 <b>{char_name}</b> покупает <b>{item_name}</b> за 🪙 {price}!"
    for pid in get_all_session_users(): await bot.send_message(pid, success_msg)
    log_message_to_db("СИСТЕМА", success_msg)

@dp.message(Command("spawn"))
async def spawn_monster(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("Формат: /spawn [ХП] [Имя]")
    args = command.args.split(maxsplit=1)
    if len(args) < 2 or not args[0].isdigit(): return await message.answer("Формат: /spawn [ХП] [Имя]")
    hp, name = int(args[0]), args[1]
    conn = sqlite3.connect('rp_database.db')
    conn.execute("INSERT INTO session_monsters (name, hp) VALUES (?, ?)", (name, hp))
    conn.commit()
    conn.close()
    msg = f"🐉 Свирепый <b>{name}</b> появляется на поле боя!"
    for pid in get_all_session_users(): await bot.send_message(pid, msg)
    log_message_to_db("СИСТЕМА", msg)

@dp.message(Command("combat_start"))
async def combat_start(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global combat_active, combat_queue, current_turn_index
    conn = sqlite3.connect('rp_database.db')
    players = conn.execute("SELECT u.user_id, u.character_name FROM users u JOIN session_players s ON u.user_id = s.user_id WHERE s.status = 'player'").fetchall()
    monsters = conn.execute("SELECT id, name FROM session_monsters").fetchall()
    conn.close()
    if not players and not monsters: return await message.answer("Нет участников для боя.")
    combat_queue = [{'type': 'player', 'id': p[0], 'name': p[1]} for p in players] + [{'type': 'monster', 'id': m[0], 'name': m[1]} for m in monsters]
    random.shuffle(combat_queue)
    combat_active = True
    current_turn_index = 0
    queue_names = [f"{i+1}. {entity['name']}" for i, entity in enumerate(combat_queue)]
    announcement = "⚔️ <b>БОЙ НАЧАЛСЯ!</b>\nИнициатива:\n\n" + "\n".join(queue_names)
    for pid in get_all_session_users(): await bot.send_message(pid, announcement)
    await announce_turn()

async def announce_turn():
    global combat_queue, current_turn_index, combat_active
    if not combat_active or not combat_queue: return
    entity = combat_queue[current_turn_index]
    msg = f"⏳ <b>ХОД ПЕРЕДАЕТСЯ:</b> <u>{entity['name']}</u>!"
    for pid in get_all_session_users(): await bot.send_message(pid, msg)

@dp.message(Command("next_turn", "next"))
async def next_turn(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global combat_active, combat_queue, current_turn_index
    if not combat_active: return await message.answer("Бой не активен.")
    current_turn_index += 1
    if current_turn_index >= len(combat_queue):
        current_turn_index = 0
        for pid in get_all_session_users(): await bot.send_message(pid, "🔄 <b>Раунд завершен! Новый круг.</b>")
    await announce_turn()

@dp.message(Command("combat_end"))
async def combat_end(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global combat_active, combat_queue, current_turn_index
    combat_active = False
    combat_queue = []
    current_turn_index = 0
    msg = "🏁 <b>Бой завершен!</b> Очередь ходов снята."
    for pid in get_all_session_users(): await bot.send_message(pid, msg)

@dp.message(Command("lore_add"))
async def lore_add_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("📚 <b>Добавление статьи</b>\nВведи название:")
    await state.set_state(GMLore.topic)

@dp.message(GMLore.topic, F.text)
async def lore_add_topic(message: types.Message, state: FSMContext):
    await state.update_data(topic=message.text.lower().strip())
    await message.answer("Отправь текст (или фото с подписью).")
    await state.set_state(GMLore.content)

@dp.message(GMLore.content)
async def lore_add_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    topic = data['topic']
    media_id, media_type, desc = None, None, message.text
    if message.photo:
        media_id, media_type, desc = message.photo[-1].file_id, 'photo', message.caption
    elif message.video:
        media_id, media_type, desc = message.video.file_id, 'video', message.caption
    if not desc: desc = "Без описания."
    conn = sqlite3.connect('rp_database.db')
    conn.execute("INSERT OR REPLACE INTO lore (topic, description, media_id, media_type) VALUES (?, ?, ?, ?)", (topic, desc, media_id, media_type))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Статья <b>{topic.capitalize()}</b> добавлена!")
    await state.clear()

@dp.message(Command("lore"))
async def read_lore(message: types.Message, command: CommandObject):
    conn = sqlite3.connect('rp_database.db')
    if not command.args:
        topics = conn.execute("SELECT topic FROM lore").fetchall()
        conn.close()
        if not topics: return await message.answer("📚 Вики пуста.")
        topics_list = "\n".join([f"🔹 <code>{t[0]}</code>" for t in topics])
        return await message.answer(f"📚 <b>ДОСТУПНЫЕ СТАТЬИ:</b>\n\n{topics_list}\n\n<i>Читай:</i> /lore [название]")
    topic = command.args.lower().strip()
    res = conn.execute("SELECT description, media_id, media_type FROM lore WHERE topic = ?", (topic,)).fetchone()
    conn.close()
    if res:
        desc, m_id, m_type = res
        header = f"📖 <b>Лор: {topic.capitalize()}</b>\n\n"
        if m_type == 'photo' and m_id: await message.answer_photo(m_id, caption=header + desc)
        elif m_type == 'video' and m_id: await message.answer_video(m_id, caption=header + desc)
        else: await message.answer(header + desc)
    else: 
        await message.answer("❓ Статьи нет.")

@dp.message(Command("roll"))
async def roll_dice(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    char_name = get_character(user_id) or "Неизвестный"
    roll = random.randint(1, 20)
    bonus = 0
    stat_name = ""
    if command.args:
        stat_request = command.args.lower().strip()
        conn = sqlite3.connect('rp_database.db')
        user_stats = conn.execute("SELECT strength, agility, intelligence FROM users WHERE user_id = ?", (user_id,)).fetchone()
        conn.close()
        if user_stats:
            s, a, i = user_stats
            if stat_request in ['str', 'сила']: bonus, stat_name = s, "(Сила)"
            elif stat_request in ['agi', 'dex', 'ловкость']: bonus, stat_name = a, "(Ловкость)"
            elif stat_request in ['int', 'интеллект']: bonus, stat_name = i, "(Интеллект)"
    total = roll + bonus
    bonus_text = f" + {bonus} {stat_name}" if bonus != 0 else ""
    text = f"🎲 <b>{char_name}</b> бросает кубик (d20): <b>{roll}</b>{bonus_text} = <b>{total}</b>"
    for pid in get_all_session_users() if get_all_session_users() else [user_id]: await bot.send_message(pid, text)

@dp.message(Command("w", "whisper", "env", "event", "npc", "as_npc", "as_gm", "broadcast"))
async def utility_commands(message: types.Message, command: CommandObject):
    cmd = message.text.split()[0].replace('/', '')
    if cmd in ['w', 'whisper']:
        if not command.args: return
        args = command.args.split(maxsplit=1)
        if len(args) < 2: return
        target_name, text = args[0], args[1]
        sender_name = get_character(message.from_user.id)
        conn = sqlite3.connect('rp_database.db')
        target_id = conn.execute("SELECT user_id FROM users WHERE character_name LIKE ?", (f"%{target_name}%",)).fetchone()
        conn.close()
        if target_id:
            await bot.send_message(target_id[0], f"🤫 <b>Шепот от [{sender_name}]:</b> {text}")
            await message.answer(f"🤫 <i>Ты прошептал {target_name}: {text}</i>")
            if message.from_user.id != ADMIN_ID and target_id[0] != ADMIN_ID: await bot.send_message(ADMIN_ID, f"👁 <i>[ПЕРЕХВАТ] {sender_name} -> {target_name}: {text}</i>")
    elif cmd == 'env' and message.from_user.id == ADMIN_ID and command.args:
        for pid in get_all_session_users(): await bot.send_message(pid, f"🌤 <i>Окружение: {command.args}</i>")
    elif cmd == 'event' and message.from_user.id == ADMIN_ID and command.args:
        for pid in get_all_session_users(): await bot.send_message(pid, f"🌌 <b>[СОБЫТИЕ]:</b>\n<i>{command.args}</i>")
    elif cmd == 'npc' and message.from_user.id == ADMIN_ID and command.args:
        args = command.args.split(maxsplit=1)
        if len(args) >= 2:
            for pid in get_all_session_users(): await bot.send_message(pid, f"🎭 <b>[{args[0]}]:</b> «{args[1]}»")
    elif cmd == 'as_npc' and message.from_user.id == ADMIN_ID and command.args:
        gm_active_npc[ADMIN_ID] = command.args
        await message.answer(f"🎭 Режим NPC: <b>{command.args}</b>")
    elif cmd == 'as_gm' and message.from_user.id == ADMIN_ID:
        gm_active_npc.pop(ADMIN_ID, None)
        await message.answer("👑 Режим NPC выключен.")
    elif cmd == 'broadcast' and message.from_user.id == ADMIN_ID:
        await message.answer("📢 Отправь пост для рассылки всем юзерам. Для отмены: /cancel")

@dp.message(Command("panel"))
async def open_gm_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('rp_database.db')
    players = conn.execute("SELECT s.user_id, u.character_name, u.hp FROM session_players s JOIN users u ON s.user_id = u.user_id WHERE s.status = 'player'").fetchall()
    monsters = conn.execute("SELECT id, name, hp FROM session_monsters").fetchall()
    conn.close()
    if not players and not monsters: return await message.answer("Нет активных существ.")
    kb = []
    for pid, name, hp in players:
        kb.append([InlineKeyboardButton(text=f"👤 {name} (❤️ {hp})", callback_data=f"gm_sel_player_{pid}")])
    for mid, name, hp in monsters:
        kb.append([InlineKeyboardButton(text=f"🐉 {name} (❤️ {hp})", callback_data=f"gm_sel_monster_{mid}")])
    await message.answer("🛠 <b>Панель Мастера</b>:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("gm_sel_"))
async def select_entity_action(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    parts = callback.data.split("_")
    target_type = parts[2]
    target_id = int(parts[3])
    await state.update_data(target_id=target_id, target_type=target_type)
    if target_type == 'player':
        kb = [
            [InlineKeyboardButton(text="⚔️ Урон", callback_data="gm_act_damage"), InlineKeyboardButton(text="💊 Подлечить", callback_data="gm_act_heal")],
            [InlineKeyboardButton(text="🎒 Дать лут", callback_data="gm_act_loot"), InlineKeyboardButton(text="🗑 Забрать лут", callback_data="gm_act_removeloot")],
            [InlineKeyboardButton(text="🪙 Дать Золото", callback_data="gm_act_addgold"), InlineKeyboardButton(text="💸 Забрать Золото", callback_data="gm_act_remgold")],
            [InlineKeyboardButton(text="✨ Опыт", callback_data="gm_act_xp"), InlineKeyboardButton(text="💖 Фулл ХП", callback_data="gm_act_fullheal")]
        ]
    else:
        kb = [
            [InlineKeyboardButton(text="⚔️ Урон", callback_data="gm_act_damage"), InlineKeyboardButton(text="💊 Хил", callback_data="gm_act_heal")],
            [InlineKeyboardButton(text="💀 Убить", callback_data="gm_act_kill")]
        ]
    await callback.message.edit_text("Выбери действие:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("gm_act_"))
async def wait_for_gm_value(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    action = callback.data.split("_")[2]
    data = await state.get_data()
    tid = data.get("target_id")
    ttype = data.get("target_type")
    
    if action == "fullheal" and ttype == 'player':
        conn = sqlite3.connect('rp_database.db')
        conn.execute("UPDATE users SET hp = 100 WHERE user_id = ?", (tid,))
        conn.commit()
        conn.close()
        for pid in get_all_session_users(): await bot.send_message(pid, f"✨ <b>{get_character(tid)}</b> полностью исцелен!")
        return await callback.message.delete()
        
    if action == "kill" and ttype == 'monster':
        conn = sqlite3.connect('rp_database.db')
        name = conn.execute("SELECT name FROM session_monsters WHERE id = ?", (tid,)).fetchone()[0]
        conn.execute("DELETE FROM session_monsters WHERE id = ?", (tid,))
        conn.commit()
        conn.close()
        for pid in get_all_session_users(): await bot.send_message(pid, f"💀 <b>{name}</b> погибает!")
        global combat_queue
        combat_queue = [q for q in combat_queue if not (q['type'] == 'monster' and q['id'] == tid)]
        return await callback.message.delete()

    await state.update_data(action_type=action)
    await state.set_state(GMAction.waiting_for_value)
    prompts = {"damage": "Урон:", "heal": "ХП:", "loot": "Предмет:", "removeloot": "Забрать предмет:", "xp": "Опыт:", "addgold": "Дать золото:", "remgold": "Забрать золото:"}
    await callback.message.edit_text(prompts[action])

@dp.message(GMAction.waiting_for_value)
async def execute_gm_action(message: types.Message, state: FSMContext):
    data = await state.get_data()
    tid = data.get("target_id")
    ttype = data.get("target_type")
    action = data.get("action_type")
    val = message.text
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    bt = ""

    if ttype == 'player':
        tname = get_character(tid)
        if action in ["damage", "heal", "xp", "addgold", "remgold"]:
            if not val.isdigit(): return await message.answer("Нужно число!")
            amt = int(val)
            cursor.execute("SELECT hp, xp, gold FROM users WHERE user_id = ?", (tid,))
            c_hp, c_xp, c_gold = cursor.fetchone()
            if action == "damage":
                cursor.execute("UPDATE users SET hp = ? WHERE user_id = ?", (c_hp - amt, tid))
                bt = f"💥 <b>{tname}</b> получает <b>{amt}</b> урона!"
            elif action == "heal":
                cursor.execute("UPDATE users SET hp = ? WHERE user_id = ?", (c_hp + amt, tid))
                bt = f"💊 <b>{tname}</b> восстанавливает <b>{amt}</b> ХП!"
            elif action == "xp":
                cursor.execute("UPDATE users SET xp = ? WHERE user_id = ?", (c_xp + amt, tid))
                bt = f"✨ <b>{tname}</b> получает <b>{amt}</b> XP!"
            elif action == "addgold":
                cursor.execute("UPDATE users SET gold = ? WHERE user_id = ?", (c_gold + amt, tid))
                bt = f"💰 <b>{tname}</b> находит 🪙 {amt} золота!"
            elif action == "remgold":
                cursor.execute("UPDATE users SET gold = ? WHERE user_id = ?", (max(0, c_gold - amt), tid))
                bt = f"💸 У <b>{tname}</b> забирают 🪙 {amt} золота."
        elif action == "loot":
            item = cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (tid, val)).fetchone()
            if item: cursor.execute("UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?", (item[0] + 1, tid, val))
            else: cursor.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (tid, val))
            bt = f"🎁 <b>{tname}</b> находит: <b>{val}</b>!"
        elif action == "removeloot":
            item = cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (tid, val)).fetchone()
            if item:
                if item[0] > 1: cursor.execute("UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?", (item[0] - 1, tid, val))
                else: cursor.execute("DELETE FROM inventory WHERE user_id = ? AND item_name = ?", (tid, val))
                bt = f"🗑 У <b>{tname}</b> забрали: <b>{val}</b>"
    elif ttype == 'monster':
        m_data = cursor.execute("SELECT name, hp FROM session_monsters WHERE id = ?", (tid,)).fetchone()
        if m_data:
            tname, c_hp = m_data
            if action in ["damage", "heal"]:
                if not val.isdigit(): return await message.answer("Нужно число!")
                amt = int(val)
                if action == "damage":
                    new_hp = c_hp - amt
                    cursor.execute("UPDATE session_monsters SET hp = ? WHERE id = ?", (new_hp, tid))
                    bt = f"💥 <b>{tname}</b> получает <b>{amt}</b> урона! (Осталось ХП: {new_hp})"
                elif action == "heal":
                    new_hp = c_hp + amt
                    cursor.execute("UPDATE session_monsters SET hp = ? WHERE id = ?", (new_hp, tid))
                    bt = f"💊 <b>{tname}</b> восстанавливает <b>{amt}</b> ХП! (ХП: {new_hp})"

    conn.commit()
    conn.close()
    if message.from_user.id in get_active_players(): await state.set_state(RPState.in_session)
    else: await state.clear()
    await message.answer("✅ Выполнено.")
    if bt:
        for pid in get_all_session_users(): await bot.send_message(pid, bt)

@dp.message(RPState.in_session)
async def rp_chat_router(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith('/'): return
    if message.from_user.id not in get_active_players():
        await state.clear()
        return await message.answer("🛑 <b>Сессия сейчас закрыта</b> или ты Зритель.")
    if message.from_user.id == ADMIN_ID and ADMIN_ID in gm_active_npc:
        char_name = gm_active_npc[ADMIN_ID]
        icon = "🎭"
    else:
        char_name = get_character(message.from_user.id)
        icon = "👤"
    formatted_text = message.text
    if formatted_text:
        formatted_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', formatted_text)
        formatted_text = re.sub(r'\((.*?)\)', r'💭 <i>\1</i>', formatted_text)
        formatted_text = re.sub(r'\"(.*?)\"', r'🗣 <b>\1</b>', formatted_text)
        formatted_text = re.sub(r'«(.*?)»', r'🗣 <b>\1</b>', formatted_text)
    final_msg = f"{icon} <b>[{char_name}]:</b> {formatted_text}" if formatted_text else None
    if formatted_text: log_message_to_db(char_name, formatted_text)
    elif message.photo or message.audio or message.voice or message.video: log_message_to_db(char_name, "[Медиафайл]")
    for pid in get_all_session_users():
        if pid != message.from_user.id:
            try:
                if message.photo: await bot.send_photo(pid, message.photo[-1].file_id, caption=f"{icon} <b>[{char_name}]:</b> {message.caption or ''}")
                elif message.audio: await bot.send_audio(pid, message.audio.file_id, caption=f"{icon} <b>[{char_name}]:</b> {message.caption or ''}")
                elif message.voice: await bot.send_voice(pid, message.voice.file_id, caption=f"{icon} <b>[{char_name}]:</b> {message.caption or ''}")
                elif message.text: await bot.send_message(pid, final_msg)
                else: 
                    await message.copy_to(pid)
                    await bot.send_message(pid, f"⬆️ <i>Отправил: {char_name}</i>")
            except Exception: pass

async def main():
    init_db()
    await set_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
