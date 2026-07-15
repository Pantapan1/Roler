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

# ==========================================
# НАСТРОЙКИ БОТА И АДМИНА
# ==========================================
TOKEN = "8656185873:AAEuggUpzeDNDZv4jtX7OkzFyey0KTLH1Tg"
ADMIN_ID = 6241704486  # Твой ID в Telegram

# Инициализация бота с настройками по умолчанию (HTML разметка)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Словарь для хранения "Маски ГМа" (Режим быстрого NPC)
# Ключ: ID ГМа, Значение: Имя активного NPC
gm_active_npc = {}

# ==========================================
# МЕНЮ КОМАНД (КНОПКА В ТЕЛЕГРАМЕ)
# ==========================================
async def set_bot_commands(bot: Bot):
    """Устанавливает команды для кнопки 'Menu' слева от поля ввода."""
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
    """Создает таблицы в БД, если их еще нет, и безопасно обновляет старые."""
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    
    # Таблица пользователей (Анкеты)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            character_name TEXT, 
            bio TEXT, 
            hp INTEGER, 
            xp INTEGER, 
            is_gm BOOLEAN
        )
    ''')
    
    # Таблица игроков/зрителей в текущей сессии
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_players (
            user_id INTEGER PRIMARY KEY, 
            status TEXT
        )
    ''')
    
    # Таблица инвентаря
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            item_name TEXT, 
            quantity INTEGER
        )
    ''')
    
    # Таблица ЛОГа для архивации
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            sender TEXT, 
            message TEXT
        )
    ''')
    
    # Таблица глобальных переменных (квесты и т.д.)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_state (
            key TEXT PRIMARY KEY, 
            value TEXT
        )
    ''')
    
    # Таблица ЛОРа (Википедии)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lore (
            topic TEXT PRIMARY KEY, 
            description TEXT
        )
    ''')
    
    # --- БЕЗОПАСНОЕ ОБНОВЛЕНИЕ БАЗЫ ---
    # Проверяем, есть ли колонки для фото/видео в лоре. Если нет - добавляем.
    cursor.execute("PRAGMA table_info(lore)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'media_id' not in columns:
        cursor.execute("ALTER TABLE lore ADD COLUMN media_id TEXT")
    if 'media_type' not in columns:
        cursor.execute("ALTER TABLE lore ADD COLUMN media_type TEXT")

    # Устанавливаем стартовый квест, если его нет
    cursor.execute("INSERT OR IGNORE INTO global_state (key, value) VALUES ('current_quest', 'Свободное исследование мира')")
    
    conn.commit()
    conn.close()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ БАЗЫ ДАННЫХ ---

def get_character(user_id):
    """Получает имя персонажа по ID пользователя."""
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT character_name FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    if res:
        return res[0]
    return None

def get_all_session_users():
    """Получает список ID всех участников сессии (игроков и зрителей)."""
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM session_players")
    res = [row[0] for row in cursor.fetchall()]
    conn.close()
    return res

def get_active_players():
    """Получает список ID только игроков (без зрителей)."""
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM session_players WHERE status = 'player'")
    res = [row[0] for row in cursor.fetchall()]
    conn.close()
    return res

def log_message_to_db(sender, text):
    """Сохраняет сообщение в таблицу логов для будущего архива."""
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

class GMLore(StatesGroup):
    topic = State()
    content = State()

# ==========================================
# ГЛОБАЛЬНАЯ ОТМЕНА ДЕЙСТВИЙ
# ==========================================
@dp.message(Command("cancel"))
async def cancel_any_action(message: types.Message, state: FSMContext):
    """Позволяет прервать любое ожидание ввода (например, при рассылке или добавлении лора)."""
    await state.clear()
    await message.answer("🛑 Действие успешно отменено.")

# ==========================================
# КОМАНДЫ: СПРАВКА И ПОМОЩЬ
# ==========================================
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Выводит список доступных команд для игроков и ГМа."""
    text = (
        "📜 <b>СПРАВОЧНИК ИГРОКА</b>\n\n"
        "🔹 /create — Создать персонажа\n"
        "🔹 /join — Зайти в сессию как Игрок\n"
        "🔹 /spectate — Зайти в сессию как Зритель\n"
        "🔹 /me — Посмотреть профиль и Инвентарь\n"
        "🔹 /lore — Открыть Вики по миру\n"
        "🔹 /quest — Посмотреть текущее задание\n"
        "🔹 <code>/w [Имя] [Текст]</code> — Шепот игроку\n"
        "🔹 /roll — Бросить кубик (d20)\n\n"
        "💡 <b>ОТЫГРЫШ:</b>\n"
        "<code>*действия*</code>, <code>(мысли)</code>, <code>\"прямая речь\"</code>.\n"
        "Можно смешивать их в одном сообщении!\n\n"
    )
    
    # Добавляем админские команды, если пишет ГМ
    if message.from_user.id == ADMIN_ID:
        text += (
            "🛠 <b>КОМАНДЫ МАСТЕРА (ГМа)</b>\n\n"
            "🔸 /open_session — Начать набор (с рассылкой всем!)\n"
            "🔸 /archive — Закрыть сессию и выгрузить лог\n"
            "🔸 /panel — Выдать урон, опыт, лут\n"
            "🔸 /lore_add — Добавить статью в Вики (с фото)\n"
            "🔸 /broadcast — Глобальная рассылка\n"
            "🔸 <code>/set_quest [Текст]</code> — Сменить задание\n"
            "🔸 <code>/env [Погода]</code> — Описать окружение\n"
            "🔸 <code>/event [Текст]</code> — Глобальное событие\n"
            "🔸 <code>/npc [Имя] [Текст]</code> — Одноразовая фраза NPC\n"
            "🔸 <code>/as_npc [Имя]</code> — Включить маску NPC (/as_gm выкл.)"
        )
    await message.answer(text)

# ==========================================
# СИСТЕМА РЕГИСТРАЦИИ ПЕРСОНАЖА
# ==========================================
@dp.message(Command("start", "create"))
async def cmd_create_char(message: types.Message, state: FSMContext):
    """Начало регистрации персонажа."""
    await message.answer("📝 Добро пожаловать в мир RL™ Nexus!\nВведи <b>Имя</b> своего героя:")
    await state.set_state(RPState.register_name)

@dp.message(RPState.register_name, F.text)
async def register_name(message: types.Message, state: FSMContext):
    """Сохраняем имя и просим био."""
    await state.update_data(char_name=message.text)
    await message.answer(f"Имя: <b>{message.text}</b>!\nТеперь опиши свой <b>Класс и биографию</b>:")
    await state.set_state(RPState.register_bio)

@dp.message(RPState.register_bio, F.text)
async def register_bio(message: types.Message, state: FSMContext):
    """Сохраняем био и записываем персонажа в базу."""
    data = await state.get_data()
    char_name = data.get("char_name")
    bio = message.text
    user_id = message.from_user.id
    is_admin = (user_id == ADMIN_ID)
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, character_name, bio, hp, xp, is_gm) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, char_name, bio, 100, 0, is_admin)
    )
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Персонаж <b>{char_name}</b> успешно создан! Жди начала сессии.")
    await state.clear()

# ==========================================
# ПОДКЛЮЧЕНИЕ К СЕССИИ
# ==========================================
@dp.message(Command("join"))
async def join_session(message: types.Message, state: FSMContext):
    """Подключение к игре в роли полноправного Игрока."""
    char_name = get_character(message.from_user.id)
    
    if not char_name:
        return await message.answer("Сначала создай персонажа через команду /create")
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO session_players (user_id, status) VALUES (?, ?)", (message.from_user.id, 'player'))
    conn.commit()
    conn.close()
    
    # Включаем перехватчик сообщений (маршрутизатор)
    await state.set_state(RPState.in_session)
    
    # Оповещаем остальных
    for pid in get_all_session_users():
        if pid != message.from_user.id:
            await bot.send_message(pid, f"<i>👤 {char_name} присоединяется к игре.</i>")
            
    await message.answer(f"✅ Ты вошел в игру как <b>{char_name}</b>.")

@dp.message(Command("spectate"))
async def spectate_session(message: types.Message):
    """Подключение к игре в роли Зрителя (без возможности писать)."""
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO session_players (user_id, status) VALUES (?, ?)", (message.from_user.id, 'spectator'))
    conn.commit()
    conn.close()
    
    await message.answer("👁 Ты подключился к сессии как зритель. Можешь читать, но не писать.")

# ==========================================
# УПРАВЛЕНИЕ СЕССИЕЙ (ГМ)
# ==========================================
@dp.message(Command("open_session"))
async def open_session(message: types.Message):
    """Открывает новую сессию и делает рассылку всем зарегистрированным."""
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM session_players") # Чистим старую комнату
    cursor.execute("DELETE FROM logs")            # Чистим логи для новой главы
    
    # Получаем всех пользователей для рассылки
    cursor.execute("SELECT user_id FROM users")
    all_registered_users = [row[0] for row in cursor.fetchall()]
    conn.commit()
    conn.close()
    
    await message.answer("🌍 Глобальная РП сессия открыта! Начинаю рассылку приглашений игрокам...")
    
    success_count = 0
    for uid in all_registered_users:
        if uid != ADMIN_ID:
            try:
                invite_text = (
                    "📢 <b>ГМ открыл набор на новую РП сессию!</b>\n\n"
                    "Пиши /join чтобы войти в игру своим персонажем, "
                    "или /spectate чтобы просто наблюдать за сюжетом."
                )
                await bot.send_message(uid, invite_text)
                success_count += 1
                await asyncio.sleep(0.05) # Защита от спам-фильтра
            except Exception:
                pass
            
    await message.answer(f"✅ Уведомления успешно разосланы ({success_count} чел.). Ждем игроков.")

@dp.message(Command("archive", "close_session"))
async def archive_and_close_session(message: types.Message, state: FSMContext):
    """Закрывает сессию, генерирует TXT файл логов и рассылает его всем участникам."""
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sender, message FROM logs")
    logs = cursor.fetchall()
    
    if not logs:
        return await message.answer("Лог пуст. Архивировать нечего.")

    # Формируем текст файла
    archive_content = "=== ХРОНИКИ СЕССИИ RL™ ===\n\n"
    for sender, text in logs:
        archive_content += f"[{sender}]: {text}\n"
        
    filename = "RL_Session_Archive.txt"
    with open(filename, "w", encoding="utf-8") as file:
        file.write(archive_content)
        
    # Рассылаем файл
    for pid in get_all_session_users():
        try:
            await bot.send_message(pid, "🛑 <b>СЕССИЯ ЗАВЕРШЕНА!</b>\nСюжет сохранен в архив.")
            await bot.send_document(pid, FSInputFile(filename))
        except Exception:
            pass

    # Очищаем комнату
    cursor.execute("DELETE FROM session_players")
    conn.commit()
    conn.close()
    
    await state.clear()
    os.remove(filename) # Удаляем локальный файл после отправки
    await message.answer("✅ Архив отправлен. Сессия успешно закрыта.")

# ==========================================
# ПРОФИЛЬ, ИНВЕНТАРЬ И КВЕСТЫ
# ==========================================
@dp.message(Command("me"))
async def check_stats(message: types.Message):
    """Показывает профиль игрока и его инвентарь."""
    user_id = message.from_user.id
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT character_name, bio, hp, xp FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        return await message.answer("Ты еще не создал персонажа. Напиши /create")
        
    char_name, bio, hp, xp = user_data
    
    # Достаем инвентарь
    cursor.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ?", (user_id,))
    items = cursor.fetchall()
    conn.close()
    
    inventory_text = "\n".join([f"🔹 {name} (x{qty})" for name, qty in items]) if items else "Пусто"
    
    text = (
        f"👤 <b>Персонаж:</b> {char_name}\n"
        f"✨ <b>Опыт:</b> {xp}\n"
        f"📜 <b>Био:</b> {bio}\n"
        f"❤️ <b>ХП:</b> {hp}\n\n"
        f"🎒 <b>Инвентарь:</b>\n{inventory_text}"
    )
    await message.answer(text)

@dp.message(Command("quest"))
async def check_quest(message: types.Message):
    """Показывает текущее глобальное задание."""
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_state WHERE key = 'current_quest'")
    quest = cursor.fetchone()
    conn.close()
    
    quest_text = quest[0] if quest else 'Нет активных заданий.'
    await message.answer(f"🎯 <b>ТЕКУЩАЯ ЦЕЛЬ:</b>\n{quest_text}")

@dp.message(Command("set_quest"))
async def set_quest(message: types.Message, command: CommandObject):
    """Устанавливает новое глобальное задание (Только для ГМа)."""
    if message.from_user.id != ADMIN_ID:
        return
    if not command.args:
        return await message.answer("Формат: /set_quest [Текст квеста]")
        
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE global_state SET value = ? WHERE key = 'current_quest'", (command.args,))
    conn.commit()
    conn.close()
    
    for pid in get_all_session_users():
        await bot.send_message(pid, f"📜 <b>ОБНОВЛЕНИЕ ЗАДАНИЯ:</b>\n{command.args}")
        
    log_message_to_db("СИСТЕМА", f"Новый квест: {command.args}")

# ==========================================
# СИСТЕМА ЛОРА (С ПОДДЕРЖКОЙ КАРТИНОК)
# ==========================================
@dp.message(Command("lore_add"))
async def lore_add_start(message: types.Message, state: FSMContext):
    """Начало процесса добавления новой статьи в Лор."""
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer("📚 <b>Добавление статьи в Вики</b>\nВведи название статьи (тему):")
    await state.set_state(GMLore.topic)

@dp.message(GMLore.topic, F.text)
async def lore_add_topic(message: types.Message, state: FSMContext):
    """Сохраняем тему и ждем контент."""
    await state.update_data(topic=message.text.lower().strip())
    
    instruction = (
        "Теперь отправь текст статьи.\n"
        "<i>💡 Если хочешь статью с картинкой — отправь фотографию "
        "и добавь к ней текст в качестве подписи.</i>"
    )
    await message.answer(instruction)
    await state.set_state(GMLore.content)

@dp.message(GMLore.content)
async def lore_add_content(message: types.Message, state: FSMContext):
    """Сохраняем контент статьи (с медиа, если есть) в базу."""
    data = await state.get_data()
    topic = data['topic']
    
    media_id = None
    media_type = None
    description = message.text
    
    # Если прислали фото
    if message.photo:
        media_id = message.photo[-1].file_id
        media_type = 'photo'
        description = message.caption
    # Если прислали видео
    elif message.video:
        media_id = message.video.file_id
        media_type = 'video'
        description = message.caption
        
    if not description:
        description = "Без описания."

    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO lore (topic, description, media_id, media_type) VALUES (?, ?, ?, ?)",
        (topic, description, media_id, media_type)
    )
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Статья <b>{topic.capitalize()}</b> успешно добавлена в Вики!")
    await state.clear()

@dp.message(Command("lore"))
async def read_lore(message: types.Message, command: CommandObject):
    """Чтение статьи из Лора или вывод списка доступных тем."""
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    
    # Если аргументов нет, выводим список всех статей
    if not command.args:
        cursor.execute("SELECT topic FROM lore")
        topics = cursor.fetchall()
        
        if not topics:
            return await message.answer("📚 Вики пока пуста.")
            
        topics_list = "\n".join([f"🔹 <code>{t[0]}</code>" for t in topics])
        await message.answer(
            f"📚 <b>ДОСТУПНЫЕ СТАТЬИ:</b>\n\n{topics_list}\n\n"
            f"<i>Скопируй название и напиши:</i> /lore [название]"
        )
        return
        
    # Если аргумент есть, ищем статью
    topic = command.args.lower().strip()
    cursor.execute("SELECT description, media_id, media_type FROM lore WHERE topic = ?", (topic,))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        desc, m_id, m_type = res
        header = f"📖 <b>Лор: {topic.capitalize()}</b>\n\n"
        
        # Отправляем с фото
        if m_type == 'photo' and m_id:
            await message.answer_photo(m_id, caption=header + desc)
        # Отправляем с видео
        elif m_type == 'video' and m_id:
            await message.answer_video(m_id, caption=header + desc)
        # Отправляем только текст
        else:
            await message.answer(header + desc)
    else: 
        await message.answer("❓ Такой статьи нет в библиотеке.")

# ==========================================
# ИГРОВЫЕ МЕХАНИКИ (Кубики, Шепот, Ивенты)
# ==========================================
@dp.message(Command("roll"))
async def roll_dice(message: types.Message):
    """Бросок d20."""
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
    """Тайное послание другому игроку (ГМ видит всё)."""
    if not command.args:
        return await message.answer("Формат: /w [Имя] [Текст]")
        
    args = command.args.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("А где текст сообщения?")
        
    target_name, text = args[0], args[1]
    sender_name = get_character(message.from_user.id)
    
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
        
        # Перехват для ГМа, если шепчутся игроки
        if message.from_user.id != ADMIN_ID and target_id != ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"👁 <i>[ПЕРЕХВАТ ШЕПОТА] {sender_name} -> {target_name}: {text}</i>")
            
        log_message_to_db("ШЕПОТ", f"{sender_name} -> {target_name}: {text}")
    else:
        await message.answer("Персонаж не найден.")

@dp.message(Command("env"))
async def set_environment(message: types.Message, command: CommandObject):
    """Установка погоды или описания окружения."""
    if message.from_user.id != ADMIN_ID or not command.args:
        return
        
    text = f"🌤 <i>Окружение: {command.args}</i>"
    for pid in get_all_session_users():
        await bot.send_message(pid, text)
        
    log_message_to_db("СИСТЕМА", text)

@dp.message(Command("event"))
async def trigger_event(message: types.Message, command: CommandObject):
    """Отправка глобального эпического события от Автора."""
    if message.from_user.id != ADMIN_ID or not command.args:
        return
        
    text = f"🌌 <b>[ГЛОБАЛЬНОЕ СОБЫТИЕ]:</b>\n<i>{command.args}</i>"
    for pid in get_all_session_users():
        await bot.send_message(pid, text)
        
    log_message_to_db("АВТОР", command.args)

# ==========================================
# ИНСТРУМЕНТЫ ГМа: УПРАВЛЕНИЕ NPC
# ==========================================
@dp.message(Command("npc"))
async def npc_speak(message: types.Message, command: CommandObject):
    """Разовая реплика от лица любого NPC."""
    if message.from_user.id != ADMIN_ID or not command.args:
        return
        
    args = command.args.split(maxsplit=1)
    if len(args) < 2:
        return
        
    npc_name, text = args[0], args[1]
    msg = f"🎭 <b>[{npc_name}]:</b> «{text}»"
    
    for pid in get_all_session_users():
        await bot.send_message(pid, msg)
        
    log_message_to_db(npc_name, text)

@dp.message(Command("as_npc"))
async def set_active_npc(message: types.Message, command: CommandObject):
    """Надеть маску NPC (все дальнейшие сообщения в чат будут от его лица)."""
    if message.from_user.id != ADMIN_ID or not command.args:
        return
        
    gm_active_npc[ADMIN_ID] = command.args
    await message.answer(f"🎭 Режим NPC включен. Вы пишете от лица: <b>{command.args}</b>\nОтключить: /as_gm")

@dp.message(Command("as_gm"))
async def disable_active_npc(message: types.Message):
    """Снять маску NPC."""
    if message.from_user.id != ADMIN_ID:
        return
        
    gm_active_npc.pop(ADMIN_ID, None)
    await message.answer("👑 Режим NPC выключен. Ты снова ГМ.")

# ==========================================
# ПАНЕЛЬ УПРАВЛЕНИЯ ИГРОКАМИ (АДМИН ПАНЕЛЬ)
# ==========================================
@dp.message(Command("panel"))
async def open_gm_panel(message: types.Message):
    """Открывает меню со списком игроков для взаимодействия."""
    if message.from_user.id != ADMIN_ID:
        return
        
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.user_id, u.character_name, u.hp 
        FROM session_players s 
        JOIN users u ON s.user_id = u.user_id 
        WHERE s.status = 'player'
    ''')
    players = cursor.fetchall()
    conn.close()

    if not players:
        return await message.answer("В сессии нет активных игроков.")

    keyboard = []
    for pid, name, hp in players:
        btn = InlineKeyboardButton(text=f"{name} (❤️ {hp})", callback_data=f"gm_select_{pid}")
        keyboard.append([btn])
        
    await message.answer("🛠 <b>Панель Мастера</b>:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data.startswith("gm_select_"))
async def select_player_action(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор игрока в панели."""
    if callback.from_user.id != ADMIN_ID:
        return
        
    await state.update_data(target_id=int(callback.data.split("_")[2]))
    
    kb = [
        [InlineKeyboardButton(text="⚔️ Урон", callback_data="gm_act_damage"), 
         InlineKeyboardButton(text="💊 Подлечить", callback_data="gm_act_heal")],
        [InlineKeyboardButton(text="🎒 Выдать лут", callback_data="gm_act_loot"), 
         InlineKeyboardButton(text="🗑 Забрать лут", callback_data="gm_act_removeloot")],
        [InlineKeyboardButton(text="✨ Опыт (XP)", callback_data="gm_act_xp"), 
         InlineKeyboardButton(text="💖 Фулл ХП", callback_data="gm_act_fullheal")]
    ]
    await callback.message.edit_text("Что делаем с персонажем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("gm_act_"))
async def wait_for_gm_value(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор действия над игроком."""
    if callback.from_user.id != ADMIN_ID:
        return
        
    action = callback.data.split("_")[2]
    
    # Действие "Полное исцеление" выполняется мгновенно
    if action == "fullheal":
        data = await state.get_data()
        tid = data.get("target_id")
        
        conn = sqlite3.connect('rp_database.db')
        conn.cursor().execute("UPDATE users SET hp = 100 WHERE user_id = ?", (tid,))
        conn.commit()
        conn.close()
        
        tname = get_character(tid)
        broadcast_text = f"✨ <b>{tname}</b> полностью исцелен!"
        
        for pid in get_all_session_users():
            await bot.send_message(pid, broadcast_text)
            
        log_message_to_db("СИСТЕМА", broadcast_text)
        return await callback.message.delete()

    # Для остальных действий запрашиваем значение
    await state.update_data(action_type=action)
    await state.set_state(GMAction.waiting_for_value)
    
    prompts = {
        "damage": "Отправь количество урона (число):",
        "heal": "Отправь количество ХП для восстановления (число):",
        "loot": "Напиши название предмета:",
        "removeloot": "Напиши название предмета, чтобы забрать:",
        "xp": "Сколько опыта (XP) выдать (число):"
    }
    await callback.message.edit_text(prompts[action])

@dp.message(GMAction.waiting_for_value)
async def execute_gm_action(message: types.Message, state: FSMContext):
    """Исполняет действие после ввода значения ГМом."""
    data = await state.get_data()
    tid = data.get("target_id")
    action = data.get("action_type")
    val = message.text
    tname = get_character(tid)
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    broadcast_text = ""

    # Обработка числовых параметров (ХП и ОПЫТ)
    if action in ["damage", "heal", "xp"]:
        if not val.isdigit():
            return await message.answer("Ошибка: Нужно отправить число!")
            
        amt = int(val)
        cursor.execute("SELECT hp, xp FROM users WHERE user_id = ?", (tid,))
        c_hp, c_xp = cursor.fetchone()
        
        if action == "damage":
            cursor.execute("UPDATE users SET hp = ? WHERE user_id = ?", (c_hp - amt, tid))
            broadcast_text = f"💥 <b>{tname}</b> получает <b>{amt}</b> урона! (ХП: {c_hp - amt})"
        elif action == "heal":
            cursor.execute("UPDATE users SET hp = ? WHERE user_id = ?", (c_hp + amt, tid))
            broadcast_text = f"💊 <b>{tname}</b> восстанавливает <b>{amt}</b> ХП! (ХП: {c_hp + amt})"
        elif action == "xp":
            cursor.execute("UPDATE users SET xp = ? WHERE user_id = ?", (c_xp + amt, tid))
            broadcast_text = f"✨ <b>{tname}</b> получает <b>{amt}</b> XP!"
            
    # Обработка инвентаря
    elif action == "loot":
        item = cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (tid, val)).fetchone()
        if item:
            cursor.execute("UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?", (item[0] + 1, tid, val))
        else:
            cursor.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (tid, val))
        broadcast_text = f"🎁 <b>{tname}</b> находит лут: <b>{val}</b>!"
        
    elif action == "removeloot":
        item = cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (tid, val)).fetchone()
        if item:
            if item[0] > 1:
                cursor.execute("UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?", (item[0] - 1, tid, val))
            else:
                cursor.execute("DELETE FROM inventory WHERE user_id = ? AND item_name = ?", (tid, val))
            broadcast_text = f"🗑 У <b>{tname}</b> забрали предмет: <b>{val}</b>"
        else:
            conn.close()
            return await message.answer("Предмет не найден у игрока. Проверьте правильность написания.")

    conn.commit()
    conn.close()
    
    # Возвращаем ГМа в сессию, если он там был
    if message.from_user.id in get_active_players():
        await state.set_state(RPState.in_session)
    else:
        await state.clear()
        
    await message.answer("✅ Действие успешно выполнено.")
    
    # Рассылка результата
    for pid in get_all_session_users():
        await bot.send_message(pid, broadcast_text)
        
    log_message_to_db("СИСТЕМА", broadcast_text)

# ==========================================
# ГЛОБАЛЬНАЯ РАССЫЛКА
# ==========================================
@dp.message(Command("broadcast"))
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📢 Отправь пост для рассылки всем юзерам. Для отмены напиши: /cancel")
    await state.set_state(GMAction.waiting_for_broadcast)

@dp.message(GMAction.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    await message.answer("⏳ Начинаю рассылку...")
    success = 0
    for uid in users:
        try:
            await message.copy_to(uid)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
            
    await state.clear()
    await message.answer(f"✅ Рассылка завершена. Доставлено: {success}")

# ==========================================
# ЯДРО СЕССИИ И ПАРСЕР ОТЫГРЫША
# ==========================================
@dp.message(RPState.in_session)
async def rp_chat_router(message: types.Message, state: FSMContext):
    """Главный маршрутизатор текстовой сессии."""
    
    # Игнорируем команды
    if message.text and message.text.startswith('/'):
        return
        
    active_players = get_active_players()
    all_session_users = get_all_session_users()
    
    # Проверка на наличие прав (вдруг сессию закрыли)
    if message.from_user.id not in active_players:
        await state.clear()
        return await message.answer("🛑 <b>Сессия сейчас закрыта</b> или ты Зритель.")
        
    # Кто пишет? (ГМ в маске или Игрок)
    if message.from_user.id == ADMIN_ID and ADMIN_ID in gm_active_npc:
        char_name = gm_active_npc[ADMIN_ID]
        icon = "🎭"
    else:
        char_name = get_character(message.from_user.id)
        icon = "👤"

    # --- УМНЫЙ ПАРСЕР ОТЫГРЫША ---
    formatted_text = message.text
    if formatted_text:
        # Заменяет *текст* на курсив (действия)
        formatted_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', formatted_text)
        
        # Заменяет (текст) на мысли
        formatted_text = re.sub(r'\((.*?)\)', r'💭 <i>\1</i>', formatted_text)
        
        # Заменяет "текст" или «текст» на прямую речь (жирным шрифтом)
        formatted_text = re.sub(r'\"(.*?)\"', r'🗣 <b>\1</b>', formatted_text)
        formatted_text = re.sub(r'«(.*?)»', r'🗣 <b>\1</b>', formatted_text)

    # Итоговый текст сообщения
    final_msg = f"{icon} <b>[{char_name}]:</b> {formatted_text}" if formatted_text else None
    
    # Запись в лог для архивации
    if formatted_text:
        log_message_to_db(char_name, formatted_text)
    elif message.photo or message.audio or message.voice or message.video:
        log_message_to_db(char_name, "[Медиафайл]")
    
    # Рассылка всем, кроме отправителя
    for pid in all_session_users:
        if pid != message.from_user.id:
            try:
                # Если это фото
                if message.photo: 
                    cap = f"{icon} <b>[{char_name}]:</b> {message.caption or ''}"
                    await bot.send_photo(pid, message.photo[-1].file_id, caption=cap)
                    
                # Если это аудио (саундтрек)
                elif message.audio: 
                    cap = f"{icon} <b>[{char_name}]:</b> {message.caption or ''}"
                    await bot.send_audio(pid, message.audio.file_id, caption=cap)
                    
                # Если это голосовое сообщение
                elif message.voice: 
                    cap = f"{icon} <b>[{char_name}]:</b> {message.caption or ''}"
                    await bot.send_voice(pid, message.voice.file_id, caption=cap)
                    
                # Если это обычный отформатированный текст
                elif message.text: 
                    await bot.send_message(pid, final_msg)
                    
                # Для стикеров, видео и других форматов
                else: 
                    await message.copy_to(pid)
                    await bot.send_message(pid, f"⬆️ <i>Отправил: {char_name}</i>")
                    
            except Exception:
                pass

# ==========================================
# ТОЧКА ВХОДА
# ==========================================
async def main():
    init_db()
    await set_bot_commands(bot)
    print("=======================================")
    print("RL™ Nexus Engine v1.2 УСПЕШНО ЗАПУЩЕН")
    print("Логика, база данных и маршрутизатор готовы.")
    print("=======================================")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
