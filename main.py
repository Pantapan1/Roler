import asyncio
import sqlite3
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand

# Твой токен от BotFather
TOKEN = "8656185873:AAEuggUpzeDNDZv4jtX7OkzFyey0KTLH1Tg"
# ID админа (ГМа)
ADMIN_ID = 6241704486

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- НАСТРОЙКА КНОПКИ MENU В TELEGRAM ---
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="create", description="📝 Создать персонажа"),
        BotCommand(command="join", description="⚔️ Войти в игру"),
        BotCommand(command="me", description="👤 Мой профиль и инвентарь"),
        BotCommand(command="lore", description="📚 Вики/Лор (Список статей)"),
        BotCommand(command="roll", description="🎲 Бросить кубик (d20)"),
        BotCommand(command="help", description="❓ Помощь и список команд")
    ]
    await bot.set_my_commands(commands)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (user_id INTEGER PRIMARY KEY, character_name TEXT, bio TEXT, hp INTEGER, is_gm BOOLEAN)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS session_players
                      (user_id INTEGER PRIMARY KEY, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, quantity INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS lore
                      (topic TEXT PRIMARY KEY, description TEXT)''')
    conn.commit()
    conn.close()

def get_character(user_id):
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT character_name FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def get_all_players_in_session():
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM session_players")
    res = [row[0] for row in cursor.fetchall()]
    conn.close()
    return res

def get_all_registered_users():
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    res = [row[0] for row in cursor.fetchall()]
    conn.close()
    return res

# --- СОСТОЯНИЯ (FSM) ---
class RPState(StatesGroup):
    register_name = State()
    register_bio = State()
    in_session = State()

class GMAction(StatesGroup):
    target_id = State()
    action_type = State()
    waiting_for_value = State()
    waiting_for_broadcast = State()

# --- ПОМОЩЬ И КОМАНДЫ ---
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📜 <b>СПРАВОЧНИК ИГРОКА</b>\n\n"
        "🔹 /create или /start — Создать персонажа\n"
        "🔹 /join — Присоединиться к активной сессии\n"
        "🔹 /me — Посмотреть свои статы, био и инвентарь\n"
        "🔹 /lore — Посмотреть список статей из лора\n"
        "🔹 <code>/lore [название]</code> — Прочитать статью\n"
        "🔹 /roll — Бросить кубик на удачу (d20)\n\n"
    )
    if message.from_user.id == ADMIN_ID:
        text += (
            "🛠 <b>КОМАНДЫ МАСТЕРА (ГМа)</b>\n\n"
            "🔸 /open_session — Начать новую сессию\n"
            "🔸 /close_session — Завершить текущую сессию\n"
            "🔸 /panel — Открыть панель управления игроками (урон/лут)\n"
            "🔸 <code>/npc [Имя] [Текст]</code> — Сказать фразу от лица NPC\n"
            "🔸 <code>/lore_add [Тема] [Текст]</code> — Добавить статью в Вики\n"
            "🔸 /broadcast — Сделать глобальную рассылку всем пользователям"
        )
    await message.answer(text)

# --- 1. РЕГИСТРАЦИЯ ПЕРСОНАЖА ---
@dp.message(Command("start", "create"))
async def cmd_create_char(message: types.Message, state: FSMContext):
    await message.answer("📝 Давай создадим персонажа!\nДля начала введи <b>Имя</b> своего героя:")
    await state.set_state(RPState.register_name)

@dp.message(RPState.register_name, F.text)
async def register_name(message: types.Message, state: FSMContext):
    await state.update_data(char_name=message.text)
    await message.answer(f"Отличное имя — <b>{message.text}</b>!\nТеперь напиши его <b>Класс и краткую биографию</b>:")
    await state.set_state(RPState.register_bio)

@dp.message(RPState.register_bio, F.text)
async def register_bio(message: types.Message, state: FSMContext):
    data = await state.get_data()
    char_name = data.get("char_name")
    bio = message.text
    user_id = message.from_user.id
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, character_name, bio, hp, is_gm) VALUES (?, ?, ?, ?, ?)",
                   (user_id, char_name, bio, 100, user_id == ADMIN_ID))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Персонаж <b>{char_name}</b> успешно создан!\nЖди, когда ГМ откроет сессию, и пиши /join.")
    await state.clear()

# --- 2. СИСТЕМА ЛОРА (Библиотека знаний) ---
@dp.message(Command("lore_add"))
async def add_lore(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("Использование: /lore_add [Тема] [Описание]")
    
    parts = command.args.split(maxsplit=1)
    if len(parts) < 2: return await message.answer("Не забудь написать само описание!")
    
    topic = parts[0].lower()
    description = parts[1]
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO lore (topic, description) VALUES (?, ?)", (topic, description))
    conn.commit()
    conn.close()
    await message.answer(f"📚 Статья <b>{topic}</b> добавлена в библиотеку ЛОРа.")

@dp.message(Command("lore", "wiki"))
async def read_lore(message: types.Message, command: CommandObject):
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    
    if not command.args:
        cursor.execute("SELECT topic FROM lore")
        topics = cursor.fetchall()
        if not topics:
            return await message.answer("📚 Библиотека ЛОРа пока пуста.")
        topics_list = "\n".join([f"🔹 <code>{t[0]}</code>" for t in topics])
        await message.answer(f"📚 <b>ДОСТУПНЫЕ СТАТЬИ В ВИКИ:</b>\n\n{topics_list}\n\n<i>Чтобы прочесть статью, нажми на её название (оно скопируется) и отправь боту команду:</i>\n/lore [название]")
        return
        
    topic = command.args.lower().strip()
    cursor.execute("SELECT description FROM lore WHERE topic = ?", (topic,))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        await message.answer(f"📖 <b>Лор: {topic.capitalize()}</b>\n\n{res[0]}")
    else:
        await message.answer("❓ Такой статьи нет в библиотеке. Проверь список по команде /lore")

# --- 3. ГЛОБАЛЬНАЯ РАССЫЛКА (BROADCAST) ---
@dp.message(Command("broadcast"))
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    await message.answer("📢 <b>Режим рассылки активирован.</b>\n"
                         "Отправь мне сообщение (текст, фото с подписью, аудио или войс), "
                         "и я разошлю его всем зарегистрированным пользователям.\n"
                         "Для отмены напиши <code>/cancel</code>.")
    await state.set_state(GMAction.waiting_for_broadcast)

@dp.message(Command("cancel"), GMAction.waiting_for_broadcast)
async def cancel_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🛑 Рассылка отменена.")

@dp.message(GMAction.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    users = get_all_registered_users()
    success_count = 0
    fail_count = 0
    
    await message.answer("⏳ Начинаю рассылку...")
    
    for user_id in users:
        try:
            await message.copy_to(user_id)
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1
            
    await state.clear()
    if message.from_user.id in get_all_players_in_session():
        await state.set_state(RPState.in_session)
        
    await message.answer(f"✅ <b>Рассылка завершена!</b>\n"
                         f"Доставлено: {success_count} чел.\n"
                         f"Не удалось доставить: {fail_count} чел.")

# --- УПРАВЛЕНИЕ СЕССИЕЙ ---
@dp.message(Command("open_session"))
async def open_session(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('rp_database.db')
    conn.cursor().execute("DELETE FROM session_players")
    conn.commit()
    conn.close()
    await message.answer("🌍 Глобальная РП сессия открыта! Игроки могут писать /join.")

@dp.message(Command("close_session", "end"))
async def close_session(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    players = get_all_players_in_session()
    if not players:
        return await message.answer("Сессия и так пуста.")
        
    # Рассылаем всем уведомление о конце сессии
    for pid in players:
        try:
            await bot.send_message(pid, "🛑 <b>ГМ завершил текущую сессию!</b>\nВсем спасибо за игру. Чат сессии закрыт.")
        except Exception:
            pass
            
    # Очищаем базу активных игроков
    conn = sqlite3.connect('rp_database.db')
    conn.cursor().execute("DELETE FROM session_players")
    conn.commit()
    conn.close()
    
    await state.clear() # Снимаем игровой стейт с ГМа
    await message.answer("✅ Сессия успешно закрыта. Все игроки отключены от чата.")

@dp.message(Command("join"))
async def join_session(message: types.Message, state: FSMContext):
    char_name = get_character(message.from_user.id)
    if not char_name:
        return await message.answer("Сначала создай персонажа через /create")
    
    conn = sqlite3.connect('rp_database.db')
    conn.cursor().execute("INSERT OR REPLACE INTO session_players (user_id, status) VALUES (?, ?)", 
                          (message.from_user.id, 'player'))
    conn.commit()
    conn.close()
    
    await state.set_state(RPState.in_session)
    
    players = get_all_players_in_session()
    for pid in players:
        if pid != message.from_user.id:
            await bot.send_message(pid, f"<i>👤 {char_name} присоединяется к игре.</i>")
    await message.answer(f"Ты вошел в игру как <b>{char_name}</b>. Теперь все твои сообщения (и фото) увидят другие.")

# --- МАСКА ГМа (NPC) ---
@dp.message(Command("npc"))
async def npc_speak(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("Формат: /npc Имя Текст")
    
    args = command.args.split(maxsplit=1)
    if len(args) < 2: return await message.answer("Забыл текст!")
    
    npc_name, text = args[0], args[1]
    for pid in get_all_players_in_session():
        await bot.send_message(pid, f"🎭 <b>[{npc_name}]:</b> «{text}»")

# --- ДАЙСЫ (Roll) ---
@dp.message(Command("roll"))
async def roll_dice(message: types.Message):
    char_name = get_character(message.from_user.id) or "Неизвестный"
    result = random.randint(1, 20)
    text = f"🎲 <b>{char_name}</b> бросает кубик (d20) и выкидывает: <b>{result}</b>"
    
    players = get_all_players_in_session()
    if message.from_user.id not in players:
        await message.answer(text)
    else:
        for pid in players:
            await bot.send_message(pid, text)

# --- ИНФО ИГРОКА ---
@dp.message(Command("me"))
async def check_stats(message: types.Message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT character_name, bio, hp FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        return await message.answer("Ты еще не создал персонажа. Напиши /create")
        
    char_name, bio, hp = user_data
    cursor.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ?", (user_id,))
    items = cursor.fetchall()
    conn.close()
    
    inventory_text = "\n".join([f"🔹 {name} (x{qty})" for name, qty in items]) if items else "Пусто"
    
    text = f"👤 <b>Персонаж:</b> {char_name}\n" \
           f"📜 <b>Био:</b> {bio}\n" \
           f"❤️ <b>Здоровье:</b> {hp}\n\n" \
           f"🎒 <b>Инвентарь:</b>\n{inventory_text}"
    await message.answer(text)

# --- АДМИН ПАНЕЛЬ ---
@dp.message(Command("panel"))
async def open_gm_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT s.user_id, u.character_name, u.hp FROM session_players s JOIN users u ON s.user_id = u.user_id''')
    active_players = cursor.fetchall()
    conn.close()

    if not active_players: return await message.answer("В сессии сейчас нет игроков.")

    keyboard = [[InlineKeyboardButton(text=f"{name} (❤️ {hp})", callback_data=f"gm_select_{pid}")] for pid, name, hp in active_players]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("🛠 <b>Панель Мастера</b>\nВыбери персонажа:", reply_markup=markup)

@dp.callback_query(F.data.startswith("gm_select_"))
async def select_player_action(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.update_data(target_id=int(callback.data.split("_")[2]))
    
    keyboard = [
        [InlineKeyboardButton(text="⚔️ Урон", callback_data="gm_action_damage"),
         InlineKeyboardButton(text="💊 Лечение", callback_data="gm_action_heal")],
        [InlineKeyboardButton(text="🎒 Выдать предмет", callback_data="gm_action_loot")]
    ]
    await callback.message.edit_text("Что делаем с персонажем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@dp.callback_query(F.data.startswith("gm_action_"))
async def wait_for_value(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    action = callback.data.split("_")[2]
    await state.update_data(action_type=action)
    await state.set_state(GMAction.waiting_for_value)
    
    prompts = {"damage": "Количество урона:", "heal": "Количество ХП:", "loot": "Название предмета:"}
    await callback.message.edit_text(prompts[action])
    await callback.answer()

@dp.message(GMAction.waiting_for_value)
async def execute_gm_action(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id, action, value = data.get("target_id"), data.get("action_type"), message.text
    target_name = get_character(target_id)
    
    conn = sqlite3.connect('rp_database.db')
    cursor = conn.cursor()
    broadcast_text = ""

    if action in ["damage", "heal"]:
        if not value.isdigit(): return await message.answer("Нужно ввести число!")
        amount = int(value)
        cursor.execute("SELECT hp FROM users WHERE user_id = ?", (target_id,))
        current_hp = cursor.fetchone()[0]
        new_hp = current_hp - amount if action == "damage" else current_hp + amount
        cursor.execute("UPDATE users SET hp = ? WHERE user_id = ?", (new_hp, target_id))
        
        broadcast_text = f"💥 <b>{target_name}</b> получает <b>{amount}</b> урона! (Осталось: {new_hp})" if action == "damage" else f"✨ <b>{target_name}</b> восстанавливает <b>{amount}</b> ХП! (Стало: {new_hp})"
    elif action == "loot":
        cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (target_id, value))
        item = cursor.fetchone()
        if item: cursor.execute("UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?", (item[0] + 1, target_id, value))
        else: cursor.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (target_id, value))
        broadcast_text = f"🎁 <b>{target_name}</b> получает предмет: <b>{value}</b>!"

    conn.commit()
    conn.close()
    await state.set_state(RPState.in_session) 
    await message.answer("Выполнено.")
    
    for pid in get_all_players_in_session(): await bot.send_message(pid, broadcast_text)

# --- МАРШРУТИЗАТОР (ПОДДЕРЖКА МЕДИА) ---
@dp.message(RPState.in_session)
async def rp_chat_router(message: types.Message, state: FSMContext):
    # Игнорируем команды
    if message.text and message.text.startswith('/'): return
        
    players = get_all_players_in_session()
    
    # ВАЖНАЯ ПРОВЕРКА: Если ГМ закрыл сессию, а у игрока остался активный стейт, 
    # бот снимет стейт и не пропустит сообщение
    if message.from_user.id not in players:
        await state.clear()
        return await message.answer("🛑 <b>Сессия сейчас закрыта.</b> Дождись, когда ГМ откроет новую!")
        
    char_name = get_character(message.from_user.id)
    
    for pid in players:
        if pid != message.from_user.id:
            try:
                if message.photo:
                    caption = f"<b>[{char_name}]:</b> {message.caption or ''}"
                    await bot.send_photo(pid, message.photo[-1].file_id, caption=caption)
                elif message.audio:
                    caption = f"<b>[{char_name}]:</b> {message.caption or ''}"
                    await bot.send_audio(pid, message.audio.file_id, caption=caption)
                elif message.voice:
                    caption = f"<b>[{char_name}]:</b> {message.caption or ''}"
                    await bot.send_voice(pid, message.voice.file_id, caption=caption)
                elif message.text:
                    await bot.send_message(pid, f"<b>[{char_name}]:</b> {message.text}")
                else:
                     await message.copy_to(pid)
                     await bot.send_message(pid, f"⬆️ <i>Отправитель: {char_name}</i>")
            except Exception:
                pass

async def main():
    init_db()
    await set_bot_commands(bot)
    print("РП Движок запущен и готов к игре...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
