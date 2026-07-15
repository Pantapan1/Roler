import asyncio
import sqlite3
import random
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from aiogram.types import FSInputFile

# ==========================================
# НАСТРОЙКИ БОТА И АДМИНА
# ==========================================
TOKEN = "8656185873:AAEuggUpzeDNDZv4jtX7OkzFyey0KTLH1Tg"
ADMIN_ID = 6241704486  # Твой ID

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Словарь для хранения "Маски ГМа" (Режим быстрого NPC)
gm_active_npc = {}

# ==========================================
# МЕНЮ КОМАНД (Синяя кнопка слева от чата)
# ==========================================
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="create", description="📝 Создать персонажа"),
        BotCommand(command="join", description="⚔️ Войти в игру (Игрок)"),
        BotCommand(command="spectate", description="👁 Войти в игру (Зритель)"),
        BotCommand(command="me", description="👤 Мой профиль и инвентарь"),
        BotCommand(command="lore", description="📚 Вики/Лор"),
        BotCommand(command="quest", description="🎯 Текущая цель"),
        BotCommand(command="roll", description="🎲 Бросить кубик (d20)"),
        BotCommand(command="help", description="❓ Помощь по командам")
    ]
    await bot.set_my_commands(commands)

# ==========================================
# БАЗА ДАННЫХ
# ==========================================
def init_db():
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    # Таблица пользователей (Добавлен XP)
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, character_name TEXT, bio TEXT, hp INTEGER, xp INTEGER, is_gm BOOLEAN)''')
    # Таблица активных сессий (status: 'player' или 'spectator')
    cursor.execute('''CREATE TABLE IF NOT EXISTS session_players 
                      (user_id INTEGER PRIMARY KEY, status TEXT)''')
    # Таблица инвентаря
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, quantity INTEGER)''')
    # Таблица ЛОРа
    cursor.execute('''CREATE TABLE IF NOT EXISTS lore 
                      (topic TEXT PRIMARY KEY, description TEXT)''')
    # Таблица логов (для Архива сессии)
    cursor.execute('''CREATE TABLE IF NOT EXISTS logs 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, message TEXT)''')
    # Глобальные переменные (Квесты, погода и т.д.)
    cursor.execute('''CREATE TABLE IF NOT EXISTS global_state 
                      (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Стартовый квест по умолчанию
    cursor.execute("INSERT OR IGNORE INTO global_state (key, value) VALUES ('current_quest', 'Свободное исследование мира')")
    conn.commit()
    conn.close()

# Вспомогательные функции БД для удобства
def get_character(user_id):
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT character_name FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def get_all_session_users():
    """Возвращает всех юзеров в комнате (и игроков, и зрителей)"""
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM session_players")
    res = [row[0] for row in cursor.fetchall()]
    conn.close()
    return res

def get_active_players():
    """Возвращает ТОЛЬКО игроков (без зрителей)"""
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM session_players WHERE status = 'player'")
    res = [row[0] for row in cursor.fetchall()]
    conn.close()
    return res

def log_message_to_db(sender, text):
    """Сохраняет сообщение в лог для будущего архива"""
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs (sender, message) VALUES (?, ?)", (sender, text))
    conn.commit()
    conn.close()

# ==========================================
# СОСТОЯНИЯ FSM (МАШИНА СОСТОЯНИЙ)
# ==========================================
class RPState(StatesGroup):
    register_name = State()
    register_bio = State()
    in_session = State()

class GMAction(StatesGroup):
    target_id = State()
    action_type = State()
    waiting_for_value = State()
    waiting_for_broadcast = State()

# ==========================================
# КОМАНДЫ: СПРАВКА И ПОМОЩЬ
# ==========================================
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📜 <b>СПРАВОЧНИК ИГРОКА</b>\n\n"
        "🔹 /create — Создать персонажа\n"
        "🔹 /join — Зайти в сессию как Игрок\n"
        "🔹 /spectate — Зайти в сессию как Зритель (только чтение)\n"
        "🔹 /me — Посмотреть профиль, ХП, Опыт и Инвентарь\n"
        "🔹 /lore — Открыть Вики по миру\n"
        "🔹 /quest — Посмотреть текущее задание группы\n"
        "🔹 <code>/w [Имя] [Текст]</code> — Скрытый шепот другому игроку\n"
        "🔹 /roll — Бросить кубик на удачу (d20)\n\n"
        "💡 <b>ОТЫГРЫШ В ЧАТЕ:</b>\n"
        "Если текст в звездочках <code>*берет меч*</code> — это действие.\n"
        "Если текст в скобках <code>(где я?)</code> — это мысли.\n"
        "Если текст в кавычках <code>\"В атаку!\"</code> — прямая речь.\n\n"
    )
    if message.from_user.id == ADMIN_ID:
        text += (
            "🛠 <b>КОМАНДЫ МАСТЕРА (ГМа)</b>\n\n"
            "🔸 /open_session — Открыть комнату для игры\n"
            "🔸 /archive — Сделать txt-архив логов и закрыть сессию\n"
            "🔸 /panel — Панель: Урон, Хил, Опыт, Выдать/Забрать лут\n"
            "🔸 /broadcast — Глобальная рассылка всем юзерам бота\n"
            "🔸 <code>/set_quest [Текст]</code> — Задать текущую цель\n"
            "🔸 <code>/env [Погода/Место]</code> — Описать окружение\n"
            "🔸 <code>/event [Текст]</code> — Эпичное событие от лица Автора\n"
            "🔸 <code>/npc [Имя] [Текст]</code> — Одноразовая фраза NPC\n"
            "🔸 <code>/as_npc [Имя]</code> — Включить режим постоянного NPC\n"
            "🔸 /as_gm — Выключить режим NPC"
        )
    await message.answer(text)

# ==========================================
# РЕГИСТРАЦИЯ ПЕРСОНАЖА
# ==========================================
@dp.message(Command("start", "create"))
async def cmd_create_char(message: types.Message, state: FSMContext):
    await message.answer("📝 Добро пожаловать в мир RL™ Nexus!\nДля начала введи <b>Имя</b> своего героя:")
    await state.set_state(RPState.register_name)

@dp.message(RPState.register_name, F.text)
async def register_name(message: types.Message, state: FSMContext):
    await state.update_data(char_name=message.text)
    await message.answer(f"Приятно познакомиться, <b>{message.text}</b>!\nТеперь кратко опиши свой <b>Класс и биографию</b>:")
    await state.set_state(RPState.register_bio)

@dp.message(RPState.register_bio, F.text)
async def register_bio(message: types.Message, state: FSMContext):
    data = await state.get_data()
    char_name = data.get("char_name")
    bio = message.text
    user_id = message.from_user.id
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, character_name, bio, hp, xp, is_gm) VALUES (?, ?, ?, ?, ?, ?)",
                   (user_id, char_name, bio, 100, 0, user_id == ADMIN_ID))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Персонаж <b>{char_name}</b> успешно создан!\nЖди, когда ГМ откроет сессию, и пиши /join.")
    await state.clear()

# ==========================================
# ПОДКЛЮЧЕНИЕ К СЕССИИ (ИГРОКИ И ЗРИТЕЛИ)
# ==========================================
@dp.message(Command("join"))
async def join_session(message: types.Message, state: FSMContext):
    char_name = get_character(message.from_user.id)
    if not char_name:
        return await message.answer("Сначала создай персонажа через /create")
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO session_players (user_id, status) VALUES (?, ?)", (message.from_user.id, 'player'))
    conn.commit()
    conn.close()
    
    await state.set_state(RPState.in_session)
    
    for pid in get_all_session_users():
        if pid != message.from_user.id:
            await bot.send_message(pid, f"<i>👤 {char_name} присоединяется к игре.</i>")
    await message.answer(f"✅ Ты вошел в игру как <b>{char_name}</b>.")

@dp.message(Command("spectate"))
async def spectate_session(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO session_players (user_id, status) VALUES (?, ?)", (message.from_user.id, 'spectator'))
    conn.commit()
    conn.close()
    
    # Зрителям не ставим in_session стейт, чтобы они не могли писать
    await message.answer("👁 Ты подключился к сессии как зритель. Ты будешь видеть все сообщения, но не сможешь писать в чат.")

# ==========================================
# УПРАВЛЕНИЕ СЕССИЕЙ И АРХИВАЦИЯ (ДЛЯ ГМа)
# ==========================================
@dp.message(Command("open_session"))
async def open_session(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM session_players") # Очищаем старую комнату
    cursor.execute("DELETE FROM logs")            # Очищаем старые логи для нового сюжета
    conn.commit()
    conn.close()
    
    await message.answer("🌍 Глобальная РП сессия открыта!\nИгроки: /join\nЗрители: /spectate")

@dp.message(Command("archive", "close_session"))
async def archive_and_close_session(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sender, message FROM logs")
    logs = cursor.fetchall()
    
    if not logs:
        return await message.answer("Лог сессии пуст. Архивировать нечего.")

    # Формируем красивый текстовый файл Хроник
    archive_content = "=== ХРОНИКИ СЕССИИ RL™ ===\n\n"
    for sender, text in logs:
        archive_content += f"[{sender}]: {text}\n"
        
    filename = "RL_Session_Archive.txt"
    with open(filename, "w", encoding="utf-8") as file:
        file.write(archive_content)
        
    # Рассылаем всем участникам и зрителям уведомление и сам файл
    for pid in get_all_session_users():
        try:
            await bot.send_message(pid, "🛑 <b>СЕССИЯ ЗАВЕРШЕНА!</b>\nСюжет сохранен в архив. Приятного чтения!")
            await bot.send_document(pid, FSInputFile(filename))
        except Exception:
            pass

    # Закрываем комнату
    cursor.execute("DELETE FROM session_players")
    conn.commit()
    conn.close()
    
    await state.clear()
    os.remove(filename) # Удаляем файл с сервера, чтобы не засорять память
    await message.answer("✅ Архив успешно сгенерирован и отправлен. Сессия закрыта.")

# ==========================================
# ИНФО И ЛОР (ПРОФИЛЬ, КВЕСТЫ, ВИКИ)
# ==========================================
@dp.message(Command("me"))
async def check_stats(message: types.Message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT character_name, bio, hp, xp FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        return await message.answer("Ты еще не создал персонажа. Напиши /create")
        
    char_name, bio, hp, xp = user_data
    
    cursor.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ?", (user_id,))
    items = cursor.fetchall()
    conn.close()
    
    inventory_text = "\n".join([f"🔹 {name} (x{qty})" for name, qty in items]) if items else "Пусто"
    
    text = f"👤 <b>Персонаж:</b> {char_name}\n" \
           f"✨ <b>Опыт (XP):</b> {xp}\n" \
           f"📜 <b>Био:</b> {bio}\n" \
           f"❤️ <b>Здоровье:</b> {hp}\n\n" \
           f"🎒 <b>Инвентарь:</b>\n{inventory_text}"
    await message.answer(text)

@dp.message(Command("quest"))
async def check_quest(message: types.Message):
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_state WHERE key = 'current_quest'")
    quest = cursor.fetchone()
    conn.close()
    
    quest_text = quest[0] if quest else "Нет активных заданий."
    await message.answer(f"🎯 <b>ТЕКУЩАЯ ЦЕЛЬ ГРУППЫ:</b>\n{quest_text}")

@dp.message(Command("set_quest"))
async def set_quest(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("Формат: /set_quest [Текст задания]")
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE global_state SET value = ? WHERE key = 'current_quest'", (command.args,))
    conn.commit()
    conn.close()
    
    # Оповещаем всех в сессии
    for pid in get_all_session_users():
        await bot.send_message(pid, f"📜 <b>ОБНОВЛЕНИЕ ЗАДАНИЯ:</b>\n{command.args}")
    log_message_to_db("СИСТЕМА", f"Новый квест: {command.args}")

@dp.message(Command("lore_add"))
async def add_lore(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("Использование: /lore_add [Тема] [Описание]")
    
    parts = command.args.split(maxsplit=1)
    if len(parts) < 2: return await message.answer("Не забудь написать само описание!")
    
    topic, description = parts[0].lower(), parts[1]
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO lore (topic, description) VALUES (?, ?)", (topic, description))
    conn.commit()
    conn.close()
    await message.answer(f"📚 Статья <b>{topic}</b> добавлена в Вики.")

@dp.message(Command("lore"))
async def read_lore(message: types.Message, command: CommandObject):
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    
    if not command.args:
        cursor.execute("SELECT topic FROM lore")
        topics = cursor.fetchall()
        if not topics: return await message.answer("📚 Вики пока пуста.")
        topics_list = "\n".join([f"🔹 <code>{t[0]}</code>" for t in topics])
        await message.answer(f"📚 <b>ДОСТУПНЫЕ СТАТЬИ В ВИКИ:</b>\n\n{topics_list}\n\n<i>Скопируй название и напиши:</i> /lore [название]")
        return
        
    topic = command.args.lower().strip()
    cursor.execute("SELECT description FROM lore WHERE topic = ?", (topic,))
    res = cursor.fetchone()
    conn.close()
    
    if res: await message.answer(f"📖 <b>Лор: {topic.capitalize()}</b>\n\n{res[0]}")
    else: await message.answer("❓ Такой статьи нет в библиотеке.")

# ==========================================
# ИГРОВЫЕ МЕХАНИКИ (Кубики, Шепот, Ивенты)
# ==========================================
@dp.message(Command("roll"))
async def roll_dice(message: types.Message):
    char_name = get_character(message.from_user.id) or "Неизвестный"
    result = random.randint(1, 20)
    text = f"🎲 <b>{char_name}</b> бросает кубик (d20) и выкидывает: <b>{result}</b>"
    
    session_users = get_all_session_users()
    if message.from_user.id not in session_users:
        await message.answer(text)
    else:
        for pid in session_users:
            await bot.send_message(pid, text)
        log_message_to_db("СИСТЕМА", f"{char_name} выбросил {result} на d20")

@dp.message(Command("w", "whisper"))
async def whisper(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /w [Имя персонажа] [Текст]")
    
    args = command.args.split(maxsplit=1)
    if len(args) < 2: return await message.answer("Забыл написать сообщение!")
    
    target_name, text = args[0], args[1]
    sender_name = get_character(message.from_user.id)
    
    # Ищем ID адресата по имени (с частичным совпадением)
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE character_name LIKE ?", (f"%{target_name}%",))
    target_data = cursor.fetchone()
    conn.close()
    
    if target_data:
        target_id = target_data[0]
        # Отправляем получателю
        await bot.send_message(target_id, f"🤫 <b>Шепот от [{sender_name}]:</b> {text}")
        # Подтверждаем отправителю
        await message.answer(f"🤫 <i>Ты прошептал персонажу {target_name}: {text}</i>")
        
        # Если ни отправитель, ни получатель не ГМ, пересылаем ГМу лог (ГМ видит всё)
        if message.from_user.id != ADMIN_ID and target_id != ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"👁 <i>[ПЕРЕХВАТ ШЕПОТА] {sender_name} -> {target_name}: {text}</i>")
            
        log_message_to_db("ШЕПОТ", f"{sender_name} -> {target_name}: {text}")
    else:
        await message.answer("Персонаж с таким именем не найден.")

@dp.message(Command("env"))
async def set_environment(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("Формат: /env [Описание погоды/места]")
    
    text = f"🌤 <i>Окружение: {command.args}</i>"
    for pid in get_all_session_users(): await bot.send_message(pid, text)
    log_message_to_db("СИСТЕМА", text)

@dp.message(Command("event"))
async def trigger_event(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("Формат: /event [Текст]")
    
    text = f"🌌 <b>[ГЛОБАЛЬНОЕ СОБЫТИЕ]:</b>\n<i>{command.args}</i>"
    for pid in get_all_session_users(): await bot.send_message(pid, text)
    log_message_to_db("АВТОР", command.args)

# ==========================================
# ИНСТРУМЕНТЫ ГМа: NPC И МАСКИ
# ==========================================
@dp.message(Command("npc"))
async def npc_speak(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("Формат: /npc [Имя] [Текст]")
    
    args = command.args.split(maxsplit=1)
    if len(args) < 2: return await message.answer("Забыл текст!")
    
    npc_name, text = args[0], args[1]
    msg = f"🎭 <b>[{npc_name}]:</b> «{text}»"
    
    for pid in get_all_session_users(): await bot.send_message(pid, msg)
    log_message_to_db(npc_name, text)

@dp.message(Command("as_npc"))
async def set_active_npc(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("Укажи имя NPC для маски.")
    
    gm_active_npc[ADMIN_ID] = command.args
    await message.answer(f"🎭 Режим NPC включен. Теперь все твои сообщения будут идти от лица: <b>{command.args}</b>\nДля отключения пиши /as_gm")

@dp.message(Command("as_gm"))
async def disable_active_npc(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    gm_active_npc.pop(ADMIN_ID, None)
    await message.answer("👑 Режим NPC выключен. Ты снова пишешь как Мастер.")

# ==========================================
# АДМИН ПАНЕЛЬ (УРОН, ЛУТ, ОПЫТ)
# ==========================================
@dp.message(Command("panel"))
async def open_gm_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    # Берем только игроков (не зрителей)
    cursor.execute('''SELECT s.user_id, u.character_name, u.hp 
                      FROM session_players s JOIN users u ON s.user_id = u.user_id 
                      WHERE s.status = 'player' ''')
    players = cursor.fetchall()
    conn.close()

    if not players: return await message.answer("В сессии сейчас нет активных игроков.")

    keyboard = []
    for pid, name, hp in players:
        btn = InlineKeyboardButton(text=f"{name} (❤️ {hp})", callback_data=f"gm_select_{pid}")
        keyboard.append([btn])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("🛠 <b>Панель Мастера</b>\nВыбери персонажа для взаимодействия:", reply_markup=markup)

@dp.callback_query(F.data.startswith("gm_select_"))
async def select_player_action(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    
    target_id = int(callback.data.split("_")[2])
    await state.update_data(target_id=target_id)
    
    # Расширенная клавиатура с новыми кнопками
    keyboard = [
        [InlineKeyboardButton(text="⚔️ Нанести урон", callback_data="gm_action_damage"),
         InlineKeyboardButton(text="💊 Подлечить", callback_data="gm_action_heal")],
        [InlineKeyboardButton(text="🎒 Выдать предмет", callback_data="gm_action_loot"),
         InlineKeyboardButton(text="🗑 Забрать лут", callback_data="gm_action_removeloot")],
        [InlineKeyboardButton(text="✨ Выдать Опыт (XP)", callback_data="gm_action_xp"),
         InlineKeyboardButton(text="💖 Полное Воскрешение", callback_data="gm_action_fullheal")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text("Что делаем с персонажем?", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data.startswith("gm_action_"))
async def wait_for_gm_value(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    action = callback.data.split("_")[2]
    
    # Полное исцеление срабатывает моментально, без ожидания ввода числа
    if action == "fullheal":
        data = await state.get_data()
        target_id = data.get("target_id")
        
        conn = sqlite3.connect('rp_database.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET hp = 100 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        
        target_name = get_character(target_id)
        broadcast_text = f"✨ <b>{target_name}</b> полностью исцелен божественным вмешательством!"
        for pid in get_all_session_users(): await bot.send_message(pid, broadcast_text)
        log_message_to_db("СИСТЕМА", broadcast_text)
        return await callback.message.delete()

    await state.update_data(action_type=action)
    await state.set_state(GMAction.waiting_for_value)
    
    prompts = {
        "damage": "Отправь количество урона:",
        "heal": "Отправь количество ХП для лечения:",
        "loot": "Отправь название предмета для выдачи:",
        "removeloot": "Отправь точное название предмета, чтобы забрать:",
        "xp": "Сколько Опыта (XP) выдать?"
    }
    await callback.message.edit_text(prompts[action])
    await callback.answer()

@dp.message(GMAction.waiting_for_value)
async def execute_gm_action(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("target_id")
    action = data.get("action_type")
    value = message.text
    target_name = get_character(target_id)
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    broadcast_text = ""

    # Обработка чисел (ХП и Опыт)
    if action in ["damage", "heal", "xp"]:
        if not value.isdigit(): return await message.answer("Нужно ввести число!")
        amount = int(value)
        
        cursor.execute("SELECT hp, xp FROM users WHERE user_id = ?", (target_id,))
        stats = cursor.fetchone()
        current_hp, current_xp = stats[0], stats[1]
        
        if action == "damage":
            new_hp = current_hp - amount
            cursor.execute("UPDATE users SET hp = ? WHERE user_id = ?", (new_hp, target_id))
            broadcast_text = f"💥 <b>{target_name}</b> получает <b>{amount}</b> урона! (ХП: {new_hp})"
        elif action == "heal":
            new_hp = current_hp + amount
            cursor.execute("UPDATE users SET hp = ? WHERE user_id = ?", (new_hp, target_id))
            broadcast_text = f"💊 <b>{target_name}</b> восстанавливает <b>{amount}</b> ХП! (ХП: {new_hp})"
        elif action == "xp":
            new_xp = current_xp + amount
            cursor.execute("UPDATE users SET xp = ? WHERE user_id = ?", (new_xp, target_id))
            broadcast_text = f"✨ <b>{target_name}</b> получает <b>{amount}</b> Опыта (XP)!"
            
    # Обработка лута (Добавление и удаление)
    elif action == "loot":
        cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (target_id, value))
        item = cursor.fetchone()
        if item: cursor.execute("UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?", (item[0] + 1, target_id, value))
        else: cursor.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (target_id, value))
        broadcast_text = f"🎁 <b>{target_name}</b> находит: <b>{value}</b>!"
        
    elif action == "removeloot":
        cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (target_id, value))
        item = cursor.fetchone()
        if item:
            if item[0] > 1: cursor.execute("UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?", (item[0] - 1, target_id, value))
            else: cursor.execute("DELETE FROM inventory WHERE user_id = ? AND item_name = ?", (target_id, value))
            broadcast_text = f"🗑 У <b>{target_name}</b> забирают предмет: <b>{value}</b>"
        else:
            conn.close()
            return await message.answer("У игрока нет такого предмета. Проверь название.")

    conn.commit()
    conn.close()
    
    # Возврат стейта
    if message.from_user.id in get_active_players(): await state.set_state(RPState.in_session)
    else: await state.clear()
        
    await message.answer("Действие выполнено.")
    
    # Рассылка и лог
    for pid in get_all_session_users(): await bot.send_message(pid, broadcast_text)
    log_message_to_db("СИСТЕМА", broadcast_text)

# ==========================================
# ГЛОБАЛЬНАЯ РАССЫЛКА (BROADCAST)
# ==========================================
@dp.message(Command("broadcast"))
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("📢 Отправь пост для рассылки всем юзерам (поддерживает медиа). Для отмены: /cancel")
    await state.set_state(GMAction.waiting_for_broadcast)

@dp.message(Command("cancel"), GMAction.waiting_for_broadcast)
async def cancel_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Рассылка отменена.")

@dp.message(GMAction.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    await message.answer("Начинаю рассылку...")
    for user_id in users:
        try:
            await message.copy_to(user_id)
            await asyncio.sleep(0.05)
        except Exception: pass
            
    await state.clear()
    await message.answer("✅ Рассылка завершена.")

# ==========================================
# ЯДРО СЕССИИ: МАРШРУТИЗАТОР И ПАРСЕР ОТЫГРЫША
# ==========================================
@dp.message(RPState.in_session)
async def rp_chat_router(message: types.Message, state: FSMContext):
    # Защита от попадания команд в чат сессии
    if message.text and message.text.startswith('/'): return
        
    active_players = get_active_players()
    all_session_users = get_all_session_users() # Игроки + Зрители
    
    # Если юзер не в списке игроков, снимаем с него стейт
    if message.from_user.id not in active_players:
        await state.clear()
        return await message.answer("🛑 <b>Сессия сейчас закрыта</b> или ты Зритель.")
        
    # Определение имени (Обычный игрок или ГМ в маске NPC)
    if message.from_user.id == ADMIN_ID and ADMIN_ID in gm_active_npc:
        char_name = gm_active_npc[ADMIN_ID]
        icon = "🎭"
    else:
        char_name = get_character(message.from_user.id)
        icon = "👤"

    # Парсинг красивого отыгрыша
    formatted_text = message.text
    if message.text:
        txt = message.text.strip()
        if txt.startswith('*') and txt.endswith('*'):
            formatted_text = f"<i>{txt}</i>"      # Курсив для действий
        elif txt.startswith('(') and txt.endswith(')'):
            formatted_text = f"💭 <i>{txt}</i>"   # Мысли
        elif txt.startswith('"') and txt.endswith('"'):
            formatted_text = f"🗣 <b>{txt}</b>"   # Прямая речь

    final_msg = f"{icon} <b>[{char_name}]:</b> {formatted_text}" if formatted_text else None
    
    # Логирование для архива
    if formatted_text: 
        log_message_to_db(char_name, formatted_text)
    elif message.photo or message.audio or message.voice or message.video:
        log_message_to_db(char_name, "[Медиафайл]")
    
    # Пересылка всем участникам комнаты (игрокам и зрителям)
    for pid in all_session_users:
        if pid != message.from_user.id:
            try:
                # Обработка фото с подписью
                if message.photo: 
                    cap = f"{icon} <b>[{char_name}]:</b> {message.caption or ''}"
                    await bot.send_photo(pid, message.photo[-1].file_id, caption=cap)
                # Обработка аудио
                elif message.audio: 
                    cap = f"{icon} <b>[{char_name}]:</b> {message.caption or ''}"
                    await bot.send_audio(pid, message.audio.file_id, caption=cap)
                # Обработка голосовых (войсов)
                elif message.voice: 
                    cap = f"{icon} <b>[{char_name}]:</b> {message.caption or ''}"
                    await bot.send_voice(pid, message.voice.file_id, caption=cap)
                # Обработка обычного и форматированного текста
                elif message.text: 
                    await bot.send_message(pid, final_msg)
                # Копирование стикеров, видео и всего остального
                else: 
                    await message.copy_to(pid)
                    await bot.send_message(pid, f"⬆️ <i>Отправил: {char_name}</i>")
            except Exception:
                pass

# ==========================================
# ЗАПУСК БОТА
# ==========================================
async def main():
    init_db()
    await set_bot_commands(bot)
    print("=======================================")
    print("RL™ Nexus Engine УСПЕШНО ЗАПУЩЕН")
    print("Логика, база данных и маршрутизатор готовы.")
    print("=======================================")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
