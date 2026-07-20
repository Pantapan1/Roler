import asyncio
import sqlite3
import random
import os
import re
import io
import time
import json
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, BotCommand, FSInputFile, BufferedInputFile
)

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ Pillow не установлен. Установи: pip install Pillow")

# ============================================
# КОНСТАНТЫ
# ============================================
TOKEN = "8656185873:AAEuggUpzeDNDZv4jtX7OkzFyey0KTLH1Tg"
SUPER_ADMIN_ID = 6241704486
DB_PATH = "rp_database.db"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

admin_router = Router()
player_router = Router()
combat_router = Router()
rp_router = Router()
room_router = Router()
gacha_router = Router()
market_router = Router()
pets_router = Router()
cards_router = Router()

dp.include_router(admin_router)
dp.include_router(combat_router)
dp.include_router(room_router)
dp.include_router(gacha_router)
dp.include_router(market_router)
dp.include_router(cards_router)
dp.include_router(pets_router)
dp.include_router(player_router)
dp.include_router(rp_router)

# ============================================
# СЕССИИ И КОМНАТЫ
# ============================================
class Session:
    def __init__(self, session_type: str = "global", room_id: int = 0):
        self.session_type = session_type
        self.room_id = room_id
        self.combat_queue: List[Dict[str, Any]] = []
        self.combat_active: bool = False
        self.current_turn_index: int = 0
        self.active_npc: Optional[str] = None
        self.current_location: str = "Стартовая локация"
        self.time_of_day: str = "день"
        self.weather: str = "ясно"
        self.ambient_text: str = ""

sessions: Dict[str, Session] = {}

def get_session_key(chat_id: int = 0, room_id: int = 0) -> str:
    if room_id > 0:
        return f"room_{room_id}"
    return f"global_{chat_id}"

def get_session(chat_id: int = 0, room_id: int = 0) -> Session:
    key = get_session_key(chat_id, room_id)
    if key not in sessions:
        sessions[key] = Session(session_type="room" if room_id > 0 else "global", room_id=room_id)
    return sessions[key]

_admins_cache: Dict[int, bool] = {}

async def is_admin(user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    if user_id in _admins_cache:
        return _admins_cache[user_id]
    res = await db_execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,), fetchone=True)
    _admins_cache[user_id] = bool(res)
    return bool(res)

def invalidate_admin_cache(user_id: int = None):
    global _admins_cache
    if user_id:
        _admins_cache.pop(user_id, None)
    else:
        _admins_cache.clear()

# ============================================
# FSM СОСТОЯНИЯ
# ============================================
class RPState(StatesGroup):
    register_name = State()
    register_bio = State()
    in_session = State()

class GMAction(StatesGroup):
    target_id = State()
    target_type = State()
    action_type = State()
    waiting_for_value = State()

class GMLore(StatesGroup):
    category = State()
    topic = State()
    content = State()
    editing_topic = State()
    editing_content = State()

class GMBroadcast(StatesGroup):
    waiting_message = State()

class GMLocation(StatesGroup):
    waiting_name = State()
    waiting_description = State()

class RoomCreate(StatesGroup):
    waiting_name = State()

class RoomInvite(StatesGroup):
    waiting_name = State()

# Gacha
class LootBoxCreate(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_items = State()

class CardPackCreate(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_cards = State()

# Market
class MarketSell(StatesGroup):
    waiting_item = State()
    waiting_price = State()

# Pets
class PetFeed(StatesGroup):
    waiting_food = State()

class PetCreate(StatesGroup):
    waiting_name = State()
    waiting_desc = State()
    waiting_rarity = State()
    waiting_stats = State()

# ============================================
# БАЗА ДАННЫХ
# ============================================
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        c = conn.cursor()
        
        # Users
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            character_name TEXT,
            bio TEXT,
            hp INTEGER DEFAULT 100,
            max_hp INTEGER DEFAULT 100,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            is_gm BOOLEAN DEFAULT 0,
            gold INTEGER DEFAULT 0,
            strength INTEGER DEFAULT 0,
            agility INTEGER DEFAULT 0,
            intelligence INTEGER DEFAULT 0,
            location TEXT DEFAULT 'Стартовая локация',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_active TEXT DEFAULT CURRENT_TIMESTAMP,
            messages_count INTEGER DEFAULT 0
        )''')
        
        # Admins
        c.execute('''CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Session players
        c.execute('''CREATE TABLE IF NOT EXISTS session_players (
            user_id INTEGER PRIMARY KEY,
            status TEXT,
            chat_id INTEGER DEFAULT 0,
            room_id INTEGER DEFAULT 0
        )''')
        
        # Monsters
        c.execute('''CREATE TABLE IF NOT EXISTS session_monsters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER DEFAULT 0,
            room_id INTEGER DEFAULT 0,
            name TEXT,
            hp INTEGER,
            max_hp INTEGER,
            attack INTEGER DEFAULT 5
        )''')
        
        # Inventory
        c.execute('''CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_name TEXT,
            quantity INTEGER,
            is_equipped BOOLEAN DEFAULT 0,
            rarity TEXT DEFAULT 'common',
            item_type TEXT DEFAULT 'item',
            UNIQUE(user_id, item_name)
        )''')
        
        # Logs
        c.execute('''CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER DEFAULT 0,
            room_id INTEGER DEFAULT 0,
            sender TEXT,
            message TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Global state
        c.execute('''CREATE TABLE IF NOT EXISTS global_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        
        # Lore
        c.execute('''CREATE TABLE IF NOT EXISTS lore (
            topic TEXT PRIMARY KEY,
            category TEXT DEFAULT 'Общее',
            description TEXT,
            media_id TEXT,
            media_type TEXT,
            views INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Lore links
        c.execute('''CREATE TABLE IF NOT EXISTS lore_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_topic TEXT,
            to_topic TEXT,
            UNIQUE(from_topic, to_topic)
        )''')
        
        # Lore history
        c.execute('''CREATE TABLE IF NOT EXISTS lore_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            editor_id INTEGER,
            old_content TEXT,
            new_content TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Market (admin)
        c.execute('''CREATE TABLE IF NOT EXISTS market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT,
            price INTEGER,
            description TEXT,
            quantity INTEGER DEFAULT 1,
            rarity TEXT DEFAULT 'common'
        )''')
        
        # Locations
        c.execute('''CREATE TABLE IF NOT EXISTS locations (
            name TEXT PRIMARY KEY,
            description TEXT,
            image_id TEXT
        )''')
        
        # Effects
        c.execute('''CREATE TABLE IF NOT EXISTS effects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            effect_name TEXT,
            duration INTEGER,
            UNIQUE(user_id, effect_name)
        )''')
        
        # Rooms
        c.execute('''CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            owner_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )''')
        
        # Room members
        c.execute('''CREATE TABLE IF NOT EXISTS room_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            user_id INTEGER,
            role TEXT DEFAULT 'member',
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(room_id, user_id)
        )''')
        
        # LOOT BOXES (Gacha)
        c.execute('''CREATE TABLE IF NOT EXISTS loot_boxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price INTEGER,
            description TEXT,
            image_id TEXT,
            is_active BOOLEAN DEFAULT 1
        )''')
        
        # Loot box items
        c.execute('''CREATE TABLE IF NOT EXISTS loot_box_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            box_id INTEGER,
            item_name TEXT,
            rarity TEXT DEFAULT 'common',
            chance REAL DEFAULT 10.0,
            quantity_min INTEGER DEFAULT 1,
            quantity_max INTEGER DEFAULT 1,
            FOREIGN KEY (box_id) REFERENCES loot_boxes(id)
        )''')
        
        # TRADING CARDS
        c.execute('''CREATE TABLE IF NOT EXISTS card_packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price INTEGER,
            description TEXT,
            image_id TEXT,
            is_active BOOLEAN DEFAULT 1
        )''')
        
        # Cards
        c.execute('''CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pack_id INTEGER,
            name TEXT,
            description TEXT,
            rarity TEXT DEFAULT 'common',
            image_id TEXT,
            stat_type TEXT,
            stat_value INTEGER DEFAULT 0,
            FOREIGN KEY (pack_id) REFERENCES card_packs(id)
        )''')
        
        # Player cards collection
        c.execute('''CREATE TABLE IF NOT EXISTS player_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            card_id INTEGER,
            quantity INTEGER DEFAULT 1,
            is_favorite BOOLEAN DEFAULT 0,
            obtained_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, card_id)
        )''')
        
        # PLAYER MARKETPLACE
        c.execute('''CREATE TABLE IF NOT EXISTS player_market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            item_name TEXT,
            price INTEGER,
            quantity INTEGER DEFAULT 1,
            rarity TEXT DEFAULT 'common',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_sold BOOLEAN DEFAULT 0
        )''')
        
        # PETS
        c.execute('''CREATE TABLE IF NOT EXISTS pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            image_id TEXT,
            rarity TEXT DEFAULT 'common',
            base_str INTEGER DEFAULT 0,
            base_agi INTEGER DEFAULT 0,
            base_int INTEGER DEFAULT 0,
            max_level INTEGER DEFAULT 10
        )''')
        
        # Player pets
        c.execute('''CREATE TABLE IF NOT EXISTS player_pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            pet_id INTEGER,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            happiness INTEGER DEFAULT 100,
            is_equipped BOOLEAN DEFAULT 0,
            obtained_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pet_id) REFERENCES pets(id)
        )''')
        
        # Pet items (food)
        c.execute('''CREATE TABLE IF NOT EXISTS pet_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            happiness_boost INTEGER DEFAULT 10,
            xp_boost INTEGER DEFAULT 0,
            price INTEGER DEFAULT 0
        )''')
        
        # Migrations
        migrations = [
            "ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE users ADD COLUMN last_active TEXT DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE users ADD COLUMN messages_count INTEGER DEFAULT 0",
            "ALTER TABLE inventory ADD COLUMN rarity TEXT DEFAULT 'common'",
            "ALTER TABLE inventory ADD COLUMN item_type TEXT DEFAULT 'item'",
            "ALTER TABLE market ADD COLUMN rarity TEXT DEFAULT 'common'",
            "ALTER TABLE lore ADD COLUMN category TEXT DEFAULT 'Общее'",
            "ALTER TABLE lore ADD COLUMN views INTEGER DEFAULT 0",
            "ALTER TABLE lore ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE lore ADD COLUMN updated_at TEXT DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE session_players ADD COLUMN room_id INTEGER DEFAULT 0",
            "ALTER TABLE session_monsters ADD COLUMN room_id INTEGER DEFAULT 0",
            "ALTER TABLE logs ADD COLUMN room_id INTEGER DEFAULT 0",
            "ALTER TABLE logs ADD COLUMN timestamp TEXT DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE locations ADD COLUMN image_id TEXT"
        ]
        
        for mig in migrations:
            try:
                c.execute(mig)
            except:
                pass
        
        # Defaults
        c.execute("INSERT OR IGNORE INTO global_state (key, value) VALUES ('current_quest', 'Свободное исследование мира')")
        c.execute("INSERT OR IGNORE INTO locations (name, description) VALUES ('Стартовая локация', 'Ты находишься в самом начале своего пути.')")
        
        # Default pet items
        c.execute("INSERT OR IGNORE INTO pet_items (name, description, happiness_boost, xp_boost, price) VALUES ('Обычный корм', 'Простая еда для питомца', 10, 5, 50)")
        c.execute("INSERT OR IGNORE INTO pet_items (name, description, happiness_boost, xp_boost, price) VALUES ('Вкусняшка', 'Любимое лакомство', 25, 15, 150)")
        c.execute("INSERT OR IGNORE INTO pet_items (name, description, happiness_boost, xp_boost, price) VALUES ('Элитный корм', 'Премиум питание', 50, 30, 500)")
        
        conn.commit()

async def db_execute(query: str, params: tuple = (), fetch: bool = False, fetchone: bool = False):
    def _do():
        with get_db() as conn:
            c = conn.cursor()
            c.execute(query, params)
            if fetch:
                return c.fetchall()
            if fetchone:
                return c.fetchone()
            conn.commit()
            return None
    return await asyncio.to_thread(_do)

async def get_character(user_id: int) -> Optional[str]:
    res = await db_execute("SELECT character_name FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    return res[0] if res else None

async def get_all_session_users(chat_id: int = 0, room_id: int = 0) -> List[int]:
    if room_id > 0:
        res = await db_execute("SELECT user_id FROM session_players WHERE room_id = ?", (room_id,), fetch=True)
    else:
        res = await db_execute("SELECT user_id FROM session_players WHERE chat_id = ? AND room_id = 0", (chat_id,), fetch=True)
    return [row[0] for row in res]

async def get_active_players(chat_id: int = 0, room_id: int = 0) -> List[int]:
    if room_id > 0:
        res = await db_execute("SELECT user_id FROM session_players WHERE status = 'player' AND room_id = ?", (room_id,), fetch=True)
    else:
        res = await db_execute("SELECT user_id FROM session_players WHERE status = 'player' AND chat_id = ? AND room_id = 0", (chat_id,), fetch=True)
    return [row[0] for row in res]

async def get_user_room(user_id: int) -> Optional[int]:
    res = await db_execute("SELECT room_id FROM session_players WHERE user_id = ? AND room_id > 0", (user_id,), fetchone=True)
    return res[0] if res else None

async def log_message(chat_id: int, sender: str, text: str, room_id: int = 0):
    await db_execute("INSERT INTO logs (chat_id, room_id, sender, message) VALUES (?, ?, ?, ?)", (chat_id, room_id, sender, text))

async def update_user_activity(user_id: int):
    await db_execute("UPDATE users SET last_active = CURRENT_TIMESTAMP, messages_count = messages_count + 1 WHERE user_id = ?", (user_id,))

# ============================================
# УТИЛИТЫ
# ============================================
RARITY_COLORS = {
    'common': (180, 180, 180),
    'uncommon': (80, 200, 80),
    'rare': (80, 140, 255),
    'epic': (180, 80, 255),
    'legendary': (255, 160, 0)
}

RARITY_ICONS = {
    'common': '',
    'uncommon': '🟢',
    'rare': '🔵',
    'epic': '🟣',
    'legendary': '🟠'
}

RARITY_NAMES = {
    'common': 'Обычный',
    'uncommon': 'Необычный',
    'rare': 'Редкий',
    'epic': 'Эпический',
    'legendary': 'Легендарный'
}

def get_font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except:
            return ImageFont.load_default()

def wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> List[str]:
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

def parse_dice(dice_str: str) -> tuple:
    dice_str = dice_str.lower().strip().replace(' ', '')
    match = re.match(r'^(\d*)d(\d+)([+-]\d+)?$', dice_str)
    if not match:
        return (1, 20, 0)
    num = int(match.group(1)) if match.group(1) else 1
    sides = int(match.group(2))
    mod = int(match.group(3)) if match.group(3) else 0
    return (num, sides, mod)

def roll_dice(dice_str: str) -> tuple:
    num, sides, mod = parse_dice(dice_str)
    if num > 100:
        num = 100
    rolls = [random.randint(1, sides) for _ in range(num)]
    return (rolls, mod, sum(rolls) + mod)

def format_rp_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'\((.*?)\)', r' <i>\1</i>', text)
    text = re.sub(r'"(.*?)"', r'🗣 <b>\1</b>', text)
    text = re.sub(r'«(.*?)»', r'🗣 <b>\1</b>', text)
    return text

async def get_session_header(chat_id: int = 0, room_id: int = 0) -> str:
    s = get_session(chat_id, room_id)
    time_icons = {"утро": "", "день": "☀️", "вечер": "🌆", "ночь": "🌙"}
    weather_icons = {"ясно": "✨", "дождь": "🌧", "снег": "❄️", "туман": "", "гроза": "⛈"}
    t_icon = time_icons.get(s.time_of_day, "☀️")
    w_icon = weather_icons.get(s.weather, "✨")
    prefix = ""
    if room_id > 0:
        room = await db_execute("SELECT name FROM rooms WHERE id = ?", (room_id,), fetchone=True)
        if room:
            prefix = f"🏠 [{room[0]}] "
    return f"{prefix}{t_icon} [{s.time_of_day.capitalize()}] {w_icon} [{s.weather.capitalize()}] 📍 [{s.current_location}]"

async def broadcast_to_session(chat_id: int, text: str, room_id: int = 0, parse_mode: str = "HTML"):
    users = await get_all_session_users(chat_id, room_id)
    for uid in users:
        try:
            await bot.send_message(uid, text, parse_mode=parse_mode)
            await asyncio.sleep(0.03)
        except Exception:
            pass

# ============================================
# ГЕНЕРАТОР КАРТИНОК
# ============================================
async def generate_character_card(user_id: int) -> Optional[BufferedInputFile]:
    if not PIL_AVAILABLE:
        return None
    try:
        user_data = await db_execute(
            "SELECT character_name, bio, hp, max_hp, xp, level, gold, strength, agility, intelligence, location FROM users WHERE user_id = ?",
            (user_id,), fetchone=True
        )
        if not user_data:
            return None
        name, bio, hp, max_hp, xp, level, gold, str_s, agi_s, int_s, location = user_data
        
        W, H = 600, 700
        img = Image.new('RGB', (W, H), color=(30, 30, 40))
        draw = ImageDraw.Draw(img)
        
        for i in range(100):
            color = (30 + i//2, 30 + i//3, 50 + i//2)
            draw.rectangle([0, i*7, W, (i+1)*7], fill=color)
        
        title_font = get_font(32)
        name_font = get_font(40)
        stat_font = get_font(20)
        small_font = get_font(16)
        
        draw.text((W//2, 30), "ПЕРСОНАЖ", font=title_font, fill=(255, 215, 0), anchor="mt")
        draw.text((W//2, 80), name, font=name_font, fill=(255, 255, 255), anchor="mt")
        draw.text((W//2, 130), f"Уровень {level}", font=stat_font, fill=(200, 200, 200), anchor="mt")
        
        y = 180
        draw.text((30, y), "❤️ HP:", font=stat_font, fill=(255, 255, 255))
        bar_x, bar_w = 120, 420
        draw.rectangle([bar_x, y, bar_x + bar_w, y + 25], fill=(50, 50, 50))
        hp_ratio = max(0, min(1, hp / max_hp)) if max_hp > 0 else 0
        hp_color = (220, 50, 50) if hp_ratio > 0.5 else (255, 150, 0) if hp_ratio > 0.2 else (200, 0, 0)
        draw.rectangle([bar_x, y, bar_x + int(bar_w * hp_ratio), y + 25], fill=hp_color)
        draw.text((bar_x + bar_w + 10, y), f"{hp}/{max_hp}", font=small_font, fill=(255, 255, 255))
        
        y += 40
        draw.text((30, y), "✨ XP:", font=stat_font, fill=(255, 255, 255))
        draw.rectangle([bar_x, y, bar_x + bar_w, y + 25], fill=(50, 50, 50))
        xp_ratio = (xp % 100) / 100
        draw.rectangle([bar_x, y, bar_x + int(bar_w * xp_ratio), y + 25], fill=(100, 150, 255))
        draw.text((bar_x + bar_w + 10, y), f"{xp}", font=small_font, fill=(255, 255, 255))
        
        y += 50
        draw.text((30, y), f"🪙 Золото: {gold}", font=stat_font, fill=(255, 215, 0))
        
        y += 50
        draw.text((30, y), "ХАРАКТЕРИСТИКИ", font=title_font, fill=(255, 215, 0))
        y += 40
        stats = [("💪 Сила", str_s, (255, 100, 100)),
                 ("🏃 Ловкость", agi_s, (100, 255, 100)),
                 ("🧠 Интеллект", int_s, (100, 150, 255))]
        for label, val, color in stats:
            draw.text((30, y), label, font=stat_font, fill=(255, 255, 255))
            draw.rectangle([200, y + 5, 200 + val * 15, y + 20], fill=color)
            draw.text((200 + val * 15 + 10, y), str(val), font=small_font, fill=(255, 255, 255))
            y += 35
        
        y += 10
        draw.text((30, y), f"📍 {location}", font=stat_font, fill=(200, 200, 200))
        
        y += 40
        draw.text((30, y), "БИОГРАФИЯ:", font=title_font, fill=(255, 215, 0))
        y += 35
        bio_lines = wrap_text(bio, small_font, W - 60, draw)
        for line in bio_lines[:5]:
            draw.text((30, y), line, font=small_font, fill=(220, 220, 220))
            y += 22
        
        draw.rectangle([5, 5, W-5, H-5], outline=(255, 215, 0), width=2)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return BufferedInputFile(buf.read(), filename="character_card.png")
    except Exception as e:
        print(f"Ошибка генерации карточки: {e}")
        return None

async def generate_card_image(card_data: tuple) -> Optional[BufferedInputFile]:
    if not PIL_AVAILABLE:
        return None
    try:
        card_id, name, description, rarity, image_id, stat_type, stat_value = card_data
        
        W, H = 400, 550
        color = RARITY_COLORS.get(rarity, RARITY_COLORS['common'])
        
        img = Image.new('RGB', (W, H), color=(20, 20, 30))
        draw = ImageDraw.Draw(img)
        
        # Рамка
        for i in range(6):
            draw.rectangle([i, i, W-i-1, H-i-1], outline=color, width=1)
        
        # Заголовок с редкостью
        rarity_names_ru = {'common': 'ОБЫЧНАЯ', 'uncommon': 'НЕОБЫЧНАЯ', 'rare': 'РЕДКАЯ', 'epic': 'ЭПИЧЕСКАЯ', 'legendary': 'ЛЕГЕНДАРНАЯ'}
        draw.rectangle([0, 0, W, 35], fill=(40, 40, 50))
        draw.text((W//2, 17), rarity_names_ru.get(rarity, 'ОБЫЧНАЯ'), font=get_font(16), fill=color, anchor="mm")
        
        # Имя
        draw.text((W//2, 70), name, font=get_font(28), fill=(255, 255, 255), anchor="mt")
        
        # Статы
        if stat_type and stat_value:
            stat_icons = {'str': '💪', 'agi': '🏃', 'int': '🧠'}
            stat_names = {'str': 'Сила', 'agi': 'Ловкость', 'int': 'Интеллект'}
            icon = stat_icons.get(stat_type, '⚡')
            sname = stat_names.get(stat_type, stat_type)
            draw.rectangle([50, 110, W-50, 145], fill=(50, 50, 60))
            draw.text((W//2, 127), f"{icon} {sname}: +{stat_value}", font=get_font(20), fill=(255, 215, 0), anchor="mm")
        
        # Описание
        draw.text((20, 170), "ОПИСАНИЕ:", font=get_font(18), fill=(200, 200, 200))
        desc_lines = wrap_text(description, get_font(16), W - 40, draw)
        y = 200
        for line in desc_lines[:8]:
            draw.text((25, y), line, font=get_font(16), fill=(230, 230, 230))
            y += 22
        
        # Декоративная линия
        draw.line([(20, y + 10), (W-20, y + 10)], fill=color, width=2)
        
        draw.text((W//2, H - 30), "COLLECTION CARD", font=get_font(14), fill=(150, 150, 150), anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return BufferedInputFile(buf.read(), filename=f"card_{card_id}.png")
    except Exception as e:
        print(f"Ошибка генерации карты: {e}")
        return None

async def generate_loot_box_image(box_data: tuple) -> Optional[BufferedInputFile]:
    if not PIL_AVAILABLE:
        return None
    try:
        box_id, name, price, description, image_id = box_data
        
        W, H = 400, 300
        img = Image.new('RGB', (W, H), color=(60, 30, 20))
        draw = ImageDraw.Draw(img)
        
        # Градиент
        for i in range(H):
            r = max(0, 60 - i//5)
            g = max(0, 30 - i//8)
            b = max(0, 20 - i//10)
            draw.line([(0, i), (W, i)], fill=(r, g, b))
        
        # Рамка
        draw.rectangle([5, 5, W-5, H-5], outline=(255, 215, 0), width=3)
        draw.rectangle([10, 10, W-10, H-10], outline=(255, 160, 0), width=1)
        
        # Название
        draw.text((W//2, 40), "🎁 СУНДУК", font=get_font(24), fill=(255, 215, 0), anchor="mt")
        draw.text((W//2, 90), name, font=get_font(32), fill=(255, 255, 255), anchor="mt")
        
        # Цена
        draw.rectangle([50, 150, W-50, 200], fill=(40, 40, 40))
        draw.text((W//2, 175), f" {price} золота", font=get_font(24), fill=(255, 215, 0), anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return BufferedInputFile(buf.read(), filename=f"lootbox_{box_id}.png")
    except Exception as e:
        print(f"Ошибка генерации сундука: {e}")
        return None

async def generate_pet_image(pet_data: tuple, level: int = 1) -> Optional[BufferedInputFile]:
    if not PIL_AVAILABLE:
        return None
    try:
        pet_id, name, description, rarity, base_str, base_agi, base_int = pet_data
        
        W, H = 400, 500
        color = RARITY_COLORS.get(rarity, RARITY_COLORS['common'])
        
        img = Image.new('RGB', (W, H), color=(25, 35, 25))
        draw = ImageDraw.Draw(img)
        
        # Рамка
        for i in range(6):
            draw.rectangle([i, i, W-i-1, H-i-1], outline=color, width=1)
        
        # Заголовок
        draw.rectangle([0, 0, W, 40], fill=(30, 40, 30))
        draw.text((W//2, 20), "🐾 ПИТОМЕЦ", font=get_font(20), fill=(200, 255, 200), anchor="mm")
        
        # Имя и уровень
        draw.text((W//2, 70), name, font=get_font(32), fill=(255, 255, 255), anchor="mt")
        draw.text((W//2, 110), f"Уровень {level}", font=get_font(22), fill=(255, 215, 0), anchor="mt")
        
        # Статы
        y = 150
        stats = [("💪 Сила", base_str + (level-1)),
                 (" Ловкость", base_agi + (level-1)),
                 ("🧠 Интеллект", base_int + (level-1))]
        
        for label, val in stats:
            draw.text((30, y), label, font=get_font(18), fill=(255, 255, 255))
            draw.rectangle([200, y + 5, 200 + min(150, val * 10), y + 20], fill=color)
            draw.text((200 + min(150, val * 10) + 10, y), str(val), font=get_font(16), fill=(255, 255, 255))
            y += 35
        
        # Описание
        draw.text((20, 280), "ОПИСАНИЕ:", font=get_font(18), fill=(200, 255, 200))
        desc_lines = wrap_text(description, get_font(15), W - 40, draw)
        y = 310
        for line in desc_lines[:7]:
            draw.text((25, y), line, font=get_font(15), fill=(230, 230, 230))
            y += 20
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return BufferedInputFile(buf.read(), filename=f"pet_{pet_id}.png")
    except Exception as e:
        print(f"Ошибка генерации питомца: {e}")
        return None

# ============================================
# КОМАНДЫ
# ============================================
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="create", description="📝 Создать персонажа"),
        BotCommand(command="join", description="⚔️ Войти в игру"),
        BotCommand(command="spectate", description="👁 Войти как зритель"),
        BotCommand(command="me", description=" Профиль (картинка)"),
        BotCommand(command="me_text", description=" Профиль (текст)"),
        BotCommand(command="market", description="🛒 Рынок ГМа"),
        BotCommand(command="player_market", description="💱 Рынок игроков"),
        BotCommand(command="use", description="🧪 Использовать предмет"),
        BotCommand(command="equip", description="🛡 Экипировать"),
        BotCommand(command="trade", description="🤝 Передать предмет"),
        BotCommand(command="lore", description="📚 Вики/Лор"),
        BotCommand(command="quest", description="🎯 Текущая цель"),
        BotCommand(command="location", description="🗺 Текущая локация"),
        BotCommand(command="roll", description="🎲 Бросить кубик"),
        BotCommand(command="w", description="🤫 Шепот игроку"),
        BotCommand(command="room_create", description="🏠 Создать комнату"),
        BotCommand(command="room_list", description="📋 Список комнат"),
        BotCommand(command="room_join", description=" Войти в комнату"),
        BotCommand(command="room_leave", description="🚪 Выйти из комнаты"),
        BotCommand(command="lootboxes", description="🎁 Сундуки с лутом"),
        BotCommand(command="cards", description="🃏 Коллекционные карты"),
        BotCommand(command="my_cards", description="📖 Моя коллекция"),
        BotCommand(command="pets", description="🐾 Питомцы"),
        BotCommand(command="my_pets", description="🐕 Мои питомцы"),
        BotCommand(command="users", description="👥 Список пользователей"),
        BotCommand(command="help", description="❓ Помощь")
    ]
    await bot.set_my_commands(commands)

# ============================================
# ОСНОВНЫЕ КОМАНДЫ
# ============================================
@admin_router.message(Command("cancel"))
@player_router.message(Command("cancel"))
@room_router.message(Command("cancel"))
@gacha_router.message(Command("cancel"))
@market_router.message(Command("cancel"))
@pets_router.message(Command("cancel"))
@cards_router.message(Command("cancel"))
async def cancel_any_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🛑 Действие отменено.")

@admin_router.message(Command("help"))
@player_router.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📜 <b>СПРАВОЧНИК ИГРОКА</b>\n\n"
        "🔹 /create — Создать персонажа\n"
        "🔹 /join | /spectate — Войти как Игрок / Зритель\n"
        "🔹 /me — Профиль (картинка)\n"
        "🔹 /me_text — Профиль (текст)\n"
        "🔹 <code>/use [Название]</code> — Использовать предмет\n"
        "🔹 <code>/equip [Название]</code> — Надеть/снять предмет\n"
        "🔹 <code>/trade [Имя] [Предмет]</code> — Передать предмет\n"
        "🔹 /market — Рынок ГМа (купить: <code>/buy [ID]</code>)\n"
        "🔹 /player_market — Рынок игроков\n"
        "🔹 <code>/sell [Предмет] [Цена]</code> — Продать на рынке\n"
        "🔹 /buy_market [ID] — Купить с рынка игроков\n"
        "🔹 /lore — Вики по миру\n"
        " /quest — Текущее задание\n"
        "🔹 /location — Текущая локация\n"
        "🔹 <code>/w [Имя] [Текст]</code> — Шепот\n"
        "🔹 <code>/roll [XdY+Z]</code> — Бросок кубика\n\n"
        
        "🏠 <b>КОМНАТЫ:</b>\n"
        "🔹 /room_create — Создать комнату\n"
        "🔹 /room_list — Список комнат\n"
        "🔹 <code>/room_join [ID]</code> — Войти\n"
        "🔹 /room_leave — Выйти\n\n"
        
        " <b>СУНДУКИ И КАРТЫ:</b>\n"
        " /lootboxes — Список сундуков\n"
        "🔹 <code>/open_loot [ID]</code> — Открыть сундук\n"
        "🔹 /cards — Пакеты карт\n"
        "🔹 <code>/open_pack [ID]</code> — Открыть пакет\n"
        "🔹 /my_cards — Моя коллекция\n\n"
        
        " <b>ПИТОМЦЫ:</b>\n"
        "🔹 /pets — Доступные питомцы\n"
        "🔹 /my_pets — Мои питомцы\n"
        "🔹 <code>/equip_pet [ID]</code> — Приручить питомца\n"
        "🔹 <code>/feed_pet [ID] [Еда]</code> — Покормить\n\n"
        
        "👥 <b>ПОЛЬЗОВАТЕЛИ:</b>\n"
        "🔹 /users — Все пользователи\n"
        "🔹 /active — Кто в сессии\n"
        "🔹 <code>/find [Имя/ID]</code> — Найти игрока\n\n"
        
        "💡 <b>ОТЫГРЫШ:</b>\n"
        "<code>*действия*</code> → <i>курсив</i>\n"
        "<code>(мысли)</code> → 💭 <i>мысли</i>\n"
        "<code>\"речь\"</code> → 🗣 <b>речь</b>\n"
    )
    
    if await is_admin(message.from_user.id):
        text += (
            "\n🛠 <b>КОМАНДЫ ГМа</b>\n\n"
            "🔸 /open_session | /archive — Сессия\n"
            "🔸 /panel — Панель управления\n"
            " /broadcast — Рассылка\n"
            "🔸 /spawn [ХП] [Имя] — Монстр\n"
            "🔸 <b>БОЙ:</b> /combat_start, /next_turn, /combat_end\n"
            "🔸 <b>РЫНОК:</b> <code>/add_market [Кол-во] [Цена] [Название] - [Описание] [Редкость]</code>\n"
            "🔸 <b>СУНДУКИ:</b> /create_lootbox, <code>/add_loot [ID сундука] [Предмет] [Редкость] [Шанс%]</code>\n"
            "🔸 <b>КАРТЫ:</b> /create_card_pack, <code>/add_card [ID пакета] [Название] [Редкость] [Шанс%]</code>\n"
            "🔸 <b>ПИТОМЦЫ:</b> /create_pet, <code>/add_pet_stat [Название] [STR] [AGI] [INT]</code>\n"
            " <b>СТАТЫ:</b> <code>/set_stats [ID] [STR] [AGI] [INT]</code>\n"
            "🔸 <b>ЛОКАЦИИ:</b> /add_location, /locations, <code>/move [Название]</code>\n"
            "🔸 <b>ВРЕМЯ:</b> <code>/time [утро/день/вечер/ночь]</code>\n"
            "🔸 <b>АДМИНЫ:</b> <code>/add_admin [ID]</code>, <code>/remove_admin [ID]</code>, /admins\n"
            "🔸 <b>ПОЛЬЗОВАТЕЛИ:</b> /dashboard, <code>/user_stats [ID]</code>\n"
            "🔸 <code>/set_quest</code>, <code>/env</code>, <code>/event</code>, <code>/npc</code>\n"
        )
    await message.answer(text)

# ============================================
# СОЗДАНИЕ ПЕРСОНАЖА
# ============================================

@admin_router.message(Command("combat_end"))
async def combat_end(message: types.Message):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    s.combat_active = False
    s.combat_queue = []
    s.current_turn_index = 0
    await broadcast_to_session(chat_id, "🏁 <b>Бой завершен!</b> Очередь ходов снята.", room_id)

@admin_router.message(Command("start", "create"))
@player_router.message(Command("start", "create"))
async def cmd_create_char(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    existing = await get_character(user_id)
    if existing:
        await message.answer(f"⚠️ У тебя уже есть персонаж: <b>{existing}</b>.\nСоздание нового сбросит статы.\nВведи имя нового героя или /cancel:")
    else:
        await message.answer("📝 Введи <b>Имя</b> своего героя:")
    await state.set_state(RPState.register_name)

@admin_router.message(RPState.register_name, F.text)
@player_router.message(RPState.register_name, F.text)
async def register_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(char_name=message.text.strip())
    await message.answer(f"Имя: <b>{message.text}</b>!\nТеперь опиши свой <b>Класс и биографию</b>:")
    await state.set_state(RPState.register_bio)

@admin_router.message(RPState.register_bio, F.text)
@player_router.message(RPState.register_bio, F.text)
async def register_bio(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    data = await state.get_data()
    char_name = data.get("char_name")
    bio = message.text
    user_id = message.from_user.id
    
    old_inv = await db_execute("SELECT item_name, quantity, is_equipped, rarity FROM inventory WHERE user_id = ?", (user_id,), fetch=True)
    
    await db_execute(
        "INSERT OR REPLACE INTO users (user_id, character_name, bio, hp, max_hp, xp, level, is_gm, gold, strength, agility, intelligence) "
        "VALUES (?, ?, ?, 100, 100, 0, 1, ?, 0, 0, 0, 0)",
        (user_id, char_name, bio, 1 if await is_admin(user_id) else 0)
    )
    
    for item in old_inv:
        await db_execute(
            "INSERT OR REPLACE INTO inventory (user_id, item_name, quantity, is_equipped, rarity) VALUES (?, ?, ?, ?, ?)",
            (user_id, item[0], item[1], item[2], item[3])
        )
    
    await message.answer(f"✅ Персонаж <b>{char_name}</b> создан!")
    await state.clear()

# ============================================
# ВХОД В СЕССИЮ
# ============================================
@admin_router.message(Command("join"))
@player_router.message(Command("join"))
async def join_session(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    user_id = message.from_user.id
    char_name = await get_character(user_id)
    if not char_name:
        return await message.answer("Сначала создай персонажа через /create")
    
    current_room = await get_user_room(user_id)
    if current_room:
        return await message.answer(f"⚠️ Ты в комнате ID {current_room}. Сначала /room_leave")
    
    await db_execute(
        "INSERT OR REPLACE INTO session_players (user_id, status, chat_id, room_id) VALUES (?, ?, ?, 0)",
        (user_id, 'player', chat_id)
    )
    await state.set_state(RPState.in_session)
    
    all_users = await get_all_session_users(chat_id)
    for pid in all_users:
        if pid != user_id:
            try:
                await bot.send_message(pid, f"<i> {char_name} присоединяется.</i>")
            except:
                pass
    await message.answer(f"✅ Ты вошел как <b>{char_name}</b>.")

@admin_router.message(Command("spectate"))
@player_router.message(Command("spectate"))
async def spectate_session(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    current_room = await get_user_room(user_id)
    if current_room:
        return await message.answer(f"⚠️ Ты в комнате ID {current_room}. Сначала /room_leave")
    
    await db_execute(
        "INSERT OR REPLACE INTO session_players (user_id, status, chat_id, room_id) VALUES (?, ?, ?, 0)",
        (user_id, 'spectator', chat_id)
    )
    await message.answer("👁 Ты зритель.")

# ============================================
# ПРОФИЛЬ
# ============================================
@admin_router.message(Command("me"))
@player_router.message(Command("me"))
async def check_stats_card(message: types.Message):
    user_id = message.from_user.id
    user_data = await db_execute("SELECT character_name FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user_data:
        return await message.answer("Сначала создай персонажа через /create")
    
    card = await generate_character_card(user_id)
    if card:
        await message.answer_photo(card, caption=f"👤 <b>{user_data[0]}</b>")
    else:
        await check_stats_text(message)

@admin_router.message(Command("me_text"))
@player_router.message(Command("me_text"))
async def check_stats_text(message: types.Message):
    user_id = message.from_user.id
    user_data = await db_execute(
        "SELECT character_name, bio, hp, max_hp, xp, level, gold, strength, agility, intelligence, location FROM users WHERE user_id = ?",
        (user_id,), fetchone=True
    )
    if not user_data:
        return await message.answer("Сначала создай персонажа через /create")
    
    name, bio, hp, max_hp, xp, level, gold, str_s, agi_s, int_s, location = user_data
    items = await db_execute("SELECT item_name, quantity, is_equipped, rarity FROM inventory WHERE user_id = ?", (user_id,), fetch=True)
    effects = await db_execute("SELECT effect_name, duration FROM effects WHERE user_id = ?", (user_id,), fetch=True)
    
    inv_list = []
    for row in items:
        prefix = "⚔️ [НАДЕТО] " if row[2] else "🔹 "
        r_icon = RARITY_ICONS.get(row[3], '⚪')
        inv_list.append(f"{prefix}{r_icon} {row[0]} (x{row[1]})")
    inv_text = "\n".join(inv_list) if inv_list else "Пусто"
    
    eff_list = [f"• {row[0]} ({row[1]} ходов)" for row in effects]
    eff_text = "\n".join(eff_list) if eff_list else "Нет"
    
    hp_bar = "█" * max(0, min(10, int(hp / max_hp * 10))) + "░" * max(0, 10 - int(hp / max_hp * 10))
    
    text = (
        f"━━━━━━━━━━━━ ⚔️ ━━━━━━━━━━━━\n"
        f"👤 <b>{name}</b> (Ур. {level})\n"
        f" {bio}\n\n"
        f"❤️ <b>HP:</b> {hp}/{max_hp} [{hp_bar}]\n"
        f"✨ <b>XP:</b> {xp} | 🪙 <b>Золото:</b> {gold}\n\n"
        f"🧬 <b>Характеристики:</b>\n"
        f"💪 Сила: {str_s} | 🏃 Ловкость: {agi_s} |  Интеллект: {int_s}\n\n"
        f"📍 <b>Локация:</b> {location}\n\n"
        f"🎒 <b>Инвентарь:</b>\n{inv_text}\n\n"
        f"🩸 <b>Эффекты:</b>\n{eff_text}\n"
        f"━━━━━━━━━━━━ ⚔️ ━━━━━━━━━━━"
    )
    await message.answer(text)

# ============================================
# ЛУТБОКСЫ (GACHA)
# ============================================
@admin_router.message(Command("create_lootbox"))
async def create_lootbox_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(" Введи <b>название</b> сундука:")
    await state.set_state(LootBoxCreate.waiting_name)

@admin_router.message(LootBoxCreate.waiting_name, F.text)
async def create_lootbox_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(box_name=message.text.strip())
    await message.answer("Введи <b>цену</b> сундука в золоте:")
    await state.set_state(LootBoxCreate.waiting_price)

@admin_router.message(LootBoxCreate.waiting_price, F.text)
async def create_lootbox_price(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    try:
        price = int(message.text.strip())
        await state.update_data(box_price=price)
        await message.answer("Введи <b>описание</b> сундука:")
        await state.set_state(LootBoxCreate.waiting_items)
    except:
        await message.answer("❌ Введи число!")

@admin_router.message(LootBoxCreate.waiting_items, F.text)
async def create_lootbox_items(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    data = await state.get_data()
    name = data['box_name']
    price = data['box_price']
    desc = message.text
    
    await db_execute(
        "INSERT INTO loot_boxes (name, price, description) VALUES (?, ?, ?)",
        (name, price, desc)
    )
    await state.clear()
    await message.answer(f"✅ Сундук <b>{name}</b> создан за {price} золота!\nТеперь добавь предметы: <code>/add_loot [ID] [Предмет] [Редкость] [Шанс%]</code>")

@admin_router.message(Command("add_loot"))
async def add_loot_to_box(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id):
        return
    args = command.args.split() if command.args else []
    if len(args) < 4:
        return await message.answer("Формат: /add_loot [ID сундука] [Предмет] [Редкость] [Шанс%]\nПример: /add_loot 1 Меч legendary 5")
    
    try:
        box_id = int(args[0])
        item_name = args[1]
        rarity = args[2].lower()
        chance = float(args[3])
        
        if rarity not in RARITY_COLORS:
            return await message.answer(f"❌ Недопустимая редкость. Варианты: {', '.join(RARITY_COLORS.keys())}")
        
        await db_execute(
            "INSERT INTO loot_box_items (box_id, item_name, rarity, chance) VALUES (?, ?, ?, ?)",
            (box_id, item_name, rarity, chance)
        )
        await message.answer(f"✅ Предмет <b>{item_name}</b> [{rarity}] добавлен в сундук с шансом {chance}%!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@admin_router.message(Command("lootboxes"))
async def list_lootboxes(message: types.Message):
    boxes = await db_execute("SELECT id, name, price, description FROM loot_boxes WHERE is_active = 1", fetch=True)
    if not boxes:
        return await message.answer("🎁 Сундуков пока нет.")
    
    text = "🎁 <b>ДОСТУПНЫЕ СУНДУКИ:</b>\n\n"
    for row in boxes:
        box_id, name, price, desc = row
        items = await db_execute("SELECT item_name, rarity, chance FROM loot_box_items WHERE box_id = ?", (box_id,), fetch=True)
        items_text = "\n".join([f"  • {RARITY_ICONS.get(r[1], '⚪')} {r[0]} ({r[2]}%)" for r in items]) if items else "  Пусто"
        text += f"🔹 <b>ID {box_id}</b> — {name}\n   💰 {price} золота\n   {desc}\n   📦 Возможный лут:\n{items_text}\n\n"
    
    text += "<i>Открыть: /open_loot [ID]</i>"
    await message.answer(text)

@admin_router.message(Command("open_loot"))
async def open_lootbox(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /open_loot [ID сундука]")
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    room_id = await get_user_room(user_id)
    box_id = int(command.args)
    
    box = await db_execute("SELECT name, price FROM loot_boxes WHERE id = ? AND is_active = 1", (box_id,), fetchone=True)
    if not box:
        return await message.answer("❌ Сундук не найден или неактивен.")
    
    name, price = box
    user_gold = await db_execute("SELECT gold FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if user_gold[0] < price:
        return await message.answer(f" Недостаточно золота. Нужно {price}, есть {user_gold[0]}.")
    
    # Списываем золото
    await db_execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (price, user_id))
    
    # Получаем предметы из сундука
    items = await db_execute("SELECT item_name, rarity, chance, quantity_min, quantity_max FROM loot_box_items WHERE box_id = ?", (box_id,), fetch=True)
    if not items:
        await db_execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (price, user_id))
        return await message.answer("❌ Сундук пуст. Золото возвращено.")
    
    # Роллим лут
    received = []
    for item in items:
        item_name, rarity, chance, q_min, q_max = item
        if random.random() * 100 <= chance:
            qty = random.randint(q_min or 1, q_max or 1)
            existing = await db_execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name), fetchone=True)
            if existing:
                await db_execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_name = ?", (qty, user_id, item_name))
            else:
                await db_execute("INSERT INTO inventory (user_id, item_name, quantity, rarity) VALUES (?, ?, ?, ?)", (user_id, item_name, qty, rarity))
            received.append(f"{RARITY_ICONS.get(rarity, '')} {item_name} x{qty}")
    
    char_name = await get_character(user_id) or "Неизвестный"
    if received:
        loot_text = "\n".join(received)
        msg = f"🎁 <b>{char_name}</b> открывает <b>{name}</b>!\n\n Получено:\n{loot_text}"
        await broadcast_to_session(chat_id, msg, room_id)
        await log_message(chat_id, "СИСТЕМА", msg, room_id)
    else:
        await message.answer(f"😢 Пусто... Попробуй ещё раз!")

# ============================================
# КОЛЛЕКЦИОННЫЕ КАРТЫ
# ============================================
@admin_router.message(Command("create_card_pack"))
async def create_card_pack_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🃏 Введи <b>название</b> пакета карт:")
    await state.set_state(CardPackCreate.waiting_name)

@admin_router.message(CardPackCreate.waiting_name, F.text)
async def create_card_pack_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(pack_name=message.text.strip())
    await message.answer("Введи <b>цену</b> пакета:")
    await state.set_state(CardPackCreate.waiting_price)

@admin_router.message(CardPackCreate.waiting_price, F.text)
async def create_card_pack_price(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    try:
        price = int(message.text.strip())
        await state.update_data(pack_price=price)
        await message.answer("Введи <b>описание</b> пакета:")
        await state.set_state(CardPackCreate.waiting_cards)
    except:
        await message.answer("❌ Введи число!")

@admin_router.message(CardPackCreate.waiting_cards, F.text)
async def create_card_pack_cards(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    data = await state.get_data()
    name = data['pack_name']
    price = data['pack_price']
    desc = message.text
    
    await db_execute(
        "INSERT INTO card_packs (name, price, description) VALUES (?, ?, ?)",
        (name, price, desc)
    )
    await state.clear()
    await message.answer(f"✅ Пакет <b>{name}</b> создан!\nДобавь карты: <code>/add_card [ID пакета] [Название] [Редкость] [Шанс%] [Тип стата] [Значение]</code>")

@admin_router.message(Command("add_card"))
async def add_card_to_pack(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id):
        return
    args = command.args.split() if command.args else []
    if len(args) < 5:
        return await message.answer("Формат: /add_card [ID пакета] [Название] [Редкость] [Шанс%] [Тип стата] [Значение]\nТипы: str/agi/int/none")
    
    try:
        pack_id = int(args[0])
        name = args[1]
        rarity = args[2].lower()
        chance = float(args[3])
        stat_type = args[4].lower() if len(args) > 4 else 'none'
        stat_value = int(args[5]) if len(args) > 5 else 0
        
        if rarity not in RARITY_COLORS:
            return await message.answer(f"❌ Недопустимая редкость.")
        if stat_type not in ['str', 'agi', 'int', 'none']:
            return await message.answer("❌ Тип стата: str/agi/int/none")
        
        await db_execute(
            "INSERT INTO cards (pack_id, name, rarity, chance, stat_type, stat_value) VALUES (?, ?, ?, ?, ?, ?)",
            (pack_id, name, rarity, chance, stat_type if stat_type != 'none' else None, stat_value)
        )
        await message.answer(f"✅ Карта <b>{name}</b> [{rarity}] добавлена!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@admin_router.message(Command("cards"))
async def list_card_packs(message: types.Message):
    packs = await db_execute("SELECT id, name, price, description FROM card_packs WHERE is_active = 1", fetch=True)
    if not packs:
        return await message.answer("🃏 Пакетов карт пока нет.")
    
    text = "🃏 <b>ПАКЕТЫ КАРТ:</b>\n\n"
    for row in packs:
        pack_id, name, price, desc = row
        cards = await db_execute("SELECT name, rarity, chance FROM cards WHERE pack_id = ?", (pack_id,), fetch=True)
        cards_text = "\n".join([f"  • {RARITY_ICONS.get(r[1], '')} {r[0]} ({r[2]}%)" for r in cards]) if cards else "  Пусто"
        text += f"🔹 <b>ID {pack_id}</b> — {name}\n   💰 {price} золота\n   {desc}\n   📦 Карты в пакете:\n{cards_text}\n\n"
    
    text += "<i>Открыть: /open_pack [ID]</i>"
    await message.answer(text)

@admin_router.message(Command("open_pack"))
async def open_card_pack(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /open_pack [ID пакета]")
    
    user_id = message.from_user.id
    pack_id = int(command.args)
    
    pack = await db_execute("SELECT name, price FROM card_packs WHERE id = ? AND is_active = 1", (pack_id,), fetchone=True)
    if not pack:
        return await message.answer(" Пакет не найден.")
    
    name, price = pack
    user_gold = await db_execute("SELECT gold FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if user_gold[0] < price:
        return await message.answer(f"❌ Недостаточно золота. Нужно {price}.")
    
    await db_execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (price, user_id))
    
    # Получаем карты
    cards = await db_execute("SELECT id, name, rarity, chance, stat_type, stat_value FROM cards WHERE pack_id = ?", (pack_id,), fetch=True)
    if not cards:
        await db_execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (price, user_id))
        return await message.answer(" Пакет пуст. Золото возвращено.")
    
    # Роллим 3 карты
    received = []
    for _ in range(3):
        total_chance = sum(c[2] for c in cards)
        roll = random.random() * total_chance
        current = 0
        selected = cards[0]
        for card in cards:
            current += card[2]
            if roll <= current:
                selected = card
                break
        
        card_id, card_name, rarity, _, stat_type, stat_value = selected
        
        # Добавляем в коллекцию
        existing = await db_execute("SELECT quantity FROM player_cards WHERE user_id = ? AND card_id = ?", (user_id, card_id), fetchone=True)
        if existing:
            await db_execute("UPDATE player_cards SET quantity = quantity + 1 WHERE user_id = ? AND card_id = ?", (user_id, card_id))
        else:
            await db_execute("INSERT INTO player_cards (user_id, card_id, quantity) VALUES (?, ?, 1)", (user_id, card_id))
        
        stat_text = f" [+{stat_value} {stat_type.upper()}]" if stat_type and stat_value else ""
        received.append(f"{RARITY_ICONS.get(rarity, '⚪')} <b>{card_name}</b>{stat_text}")
    
    char_name = await get_character(user_id) or "Неизвестный"
    cards_list = "\n".join(received)
    await message.answer(f"🃏 <b>{char_name}</b> открывает пакет <b>{name}</b>!\n\n🎴 Получено:\n{cards_list}")

@admin_router.message(Command("my_cards"))
async def my_cards_collection(message: types.Message):
    user_id = message.from_user.id
    cards = await db_execute(
        "SELECT c.name, c.rarity, c.description, c.stat_type, c.stat_value, pc.quantity, pc.is_favorite "
        "FROM player_cards pc JOIN cards c ON pc.card_id = c.id WHERE pc.user_id = ? ORDER BY c.rarity DESC, c.name",
        (user_id,), fetch=True
    )
    if not cards:
        return await message.answer(" У тебя нет карт. Открой пакеты через /cards")
    
    text = "📖 <b>ТВОЯ КОЛЛЕКЦИЯ:</b>\n\n"
    for row in cards:
        name, rarity, desc, stat_type, stat_value, qty, fav = row
        fav_icon = "⭐ " if fav else ""
        stat_text = f" [+{stat_value} {stat_type.upper()}]" if stat_type and stat_value else ""
        text += f"{fav_icon}{RARITY_ICONS.get(rarity, '⚪')} <b>{name}</b> x{qty}{stat_text}\n<i>{desc[:60]}...</i>\n\n"
    
    text += "<i>Избранное: /fav_card [Название]</i>"
    await message.answer(text)

@admin_router.message(Command("fav_card"))
async def favorite_card(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Формат: /fav_card [Название карты]")
    
    user_id = message.from_user.id
    card_name = command.args.strip()
    
    card = await db_execute(
        "SELECT pc.id FROM player_cards pc JOIN cards c ON pc.card_id = c.id WHERE pc.user_id = ? AND c.name = ?",
        (user_id, card_name), fetchone=True
    )
    if not card:
        return await message.answer("❌ Карта не найдена.")
    
    current = await db_execute("SELECT is_favorite FROM player_cards WHERE id = ?", (card[0],), fetchone=True)
    await db_execute("UPDATE player_cards SET is_favorite = ? WHERE id = ?", (not current[0], card[0]))
    status = "добавлена" if not current[0] else "убрана"
    await message.answer(f"✅ Карта {status} в избранное!")

# ============================================
# ПИТОМЦЫ
# ============================================
@admin_router.message(Command("create_pet"))
async def create_pet_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🐾 Введи <b>название</b> питомца:")
    await state.set_state(PetCreate.waiting_name)

@admin_router.message(PetCreate.waiting_name, F.text)
async def create_pet_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(pet_name=message.text.strip())
    await message.answer("Введи <b>описание</b> питомца:")
    await state.set_state(PetCreate.waiting_desc)

@admin_router.message(PetCreate.waiting_desc, F.text)
async def create_pet_desc(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(pet_desc=message.text)
    await message.answer("Введи <b>редкость</b> (common/uncommon/rare/epic/legendary):")
    await state.set_state(PetCreate.waiting_rarity)

@admin_router.message(PetCreate.waiting_rarity, F.text)
async def create_pet_rarity(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    rarity = message.text.lower().strip()
    if rarity not in RARITY_COLORS:
        return await message.answer("❌ Недопустимая редкость.")
    await state.update_data(pet_rarity=rarity)
    await message.answer("Введи <b>базовые статы</b> в формате: [STR] [AGI] [INT]\nПример: 5 3 2")
    await state.set_state(PetCreate.waiting_stats)

@admin_router.message(PetCreate.waiting_stats, F.text)
async def create_pet_stats(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("❌ Формат: [STR] [AGI] [INT]")
    
    try:
        str_s, agi_s, int_s = map(int, args[:3])
        data = await state.get_data()
        
        await db_execute(
            "INSERT INTO pets (name, description, rarity, base_str, base_agi, base_int) VALUES (?, ?, ?, ?, ?, ?)",
            (data['pet_name'], data['pet_desc'], data['pet_rarity'], str_s, agi_s, int_s)
        )
        await state.clear()
        await message.answer(f"✅ Питомец <b>{data['pet_name']}</b> создан!")
    except Exception as e:
        await message.answer(f" Ошибка: {e}")

@admin_router.message(Command("add_pet_stat"))
async def add_pet_stat(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id):
        return
    args = command.args.split() if command.args else []
    if len(args) < 4:
        return await message.answer("Формат: /add_pet_stat [Название питомца] [STR] [AGI] [INT]")
    
    try:
        name = args[0]
        str_s, agi_s, int_s = map(int, args[1:4])
        await db_execute(
            "UPDATE pets SET base_str=?, base_agi=?, base_int=? WHERE name=?",
            (str_s, agi_s, int_s, name)
        )
        await message.answer(f"✅ Статы питомца <b>{name}</b> обновлены!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@admin_router.message(Command("pets"))
async def list_pets(message: types.Message):
    pets = await db_execute("SELECT name, description, rarity, base_str, base_agi, base_int, max_level FROM pets", fetch=True)
    if not pets:
        return await message.answer("🐾 Питомцев пока нет.")
    
    text = "🐾 <b>ДОСТУПНЫЕ ПИТОМЦЫ:</b>\n\n"
    for row in pets:
        name, desc, rarity, str_s, agi_s, int_s, max_lvl = row
        text += f"{RARITY_ICONS.get(rarity, '⚪')} <b>{name}</b> [{RARITY_NAMES.get(rarity, 'Обычный')}]\n"
        text += f"   💪 {str_s} | 🏃 {agi_s} |  {int_s}\n"
        text += f"   Макс. уровень: {max_lvl}\n"
        text += f"   <i>{desc}</i>\n\n"
    
    text += "<i>Приручить: /tame_pet [Название]</i>"
    await message.answer(text)

@admin_router.message(Command("tame_pet"))
async def tame_pet(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Формат: /tame_pet [Название питомца]")
    
    user_id = message.from_user.id
    pet_name = command.args.strip()
    
    pet = await db_execute("SELECT id, name FROM pets WHERE name = ?", (pet_name,), fetchone=True)
    if not pet:
        return await message.answer("❌ Питомец не найден.")
    
    existing = await db_execute("SELECT 1 FROM player_pets WHERE user_id = ? AND pet_id = ?", (user_id, pet[0]), fetchone=True)
    if existing:
        return await message.answer("⚠️ У тебя уже есть этот питомец!")
    
    await db_execute("INSERT INTO player_pets (user_id, pet_id) VALUES (?, ?)", (user_id, pet[0]))
    await message.answer(f"✅ Ты приручил <b>{pet[1]}</b>! Смотри /my_pets")

@admin_router.message(Command("my_pets"))
async def my_pets(message: types.Message):
    user_id = message.from_user.id
    pets = await db_execute(
        "SELECT p.name, p.rarity, p.base_str, p.base_agi, p.base_int, pp.level, pp.xp, pp.happiness, pp.is_equipped "
        "FROM player_pets pp JOIN pets p ON pp.pet_id = p.id WHERE pp.user_id = ?",
        (user_id,), fetch=True
    )
    if not pets:
        return await message.answer(" У тебя нет питомцев. Смотри /pets")
    
    text = "🐕 <b>ТВОИ ПИТОМЦЫ:</b>\n\n"
    for row in pets:
        name, rarity, str_s, agi_s, int_s, level, xp, happiness, equipped = row
        eq_icon = "⚔️ " if equipped else ""
        happiness_icon = "😊" if happiness > 70 else "😐" if happiness > 30 else "😢"
        
        # Статы с учетом уровня
        total_str = str_s + (level - 1)
        total_agi = agi_s + (level - 1)
        total_int = int_s + (level - 1)
        
        text += f"{eq_icon}{RARITY_ICONS.get(rarity, '⚪')} <b>{name}</b> (Ур. {level}) {happiness_icon}\n"
        text += f"   💪 {total_str} |  {total_agi} | 🧠 {total_int}\n"
        text += f"   ✨ XP: {xp}/100 | ❤️ Счастье: {happiness}/100\n\n"
    
    text += "<i>Экипировать: /equip_pet [Название]\nПокормить: /feed_pet [Название] [Еда]</i>"
    await message.answer(text)

@admin_router.message(Command("equip_pet"))
async def equip_pet(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Формат: /equip_pet [Название питомца]")
    
    user_id = message.from_user.id
    pet_name = command.args.strip()
    
    # Снимаем со всех
    await db_execute("UPDATE player_pets SET is_equipped = 0 WHERE user_id = ?", (user_id,))
    
    # Надеваем на нужного
    pet = await db_execute(
        "SELECT pp.id FROM player_pets pp JOIN pets p ON pp.pet_id = p.id WHERE pp.user_id = ? AND p.name = ?",
        (user_id, pet_name), fetchone=True
    )
    if not pet:
        return await message.answer(" Питомец не найден.")
    
    await db_execute("UPDATE player_pets SET is_equipped = 1 WHERE id = ?", (pet[0],))
    await message.answer(f"✅ <b>{pet_name}</b> теперь твой спутник!")

@admin_router.message(Command("feed_pet"))
async def feed_pet(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Формат: /feed_pet [Название питомца] [Еда]")
    
    user_id = message.from_user.id
    args = command.args.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("Формат: /feed_pet [Название] [Еда]")
    
    pet_name, food_name = args[0], args[1]
    
    pet = await db_execute(
        "SELECT pp.id, pp.happiness FROM player_pets pp JOIN pets p ON pp.pet_id = p.id WHERE pp.user_id = ? AND p.name = ?",
        (user_id, pet_name), fetchone=True
    )
    if not pet:
        return await message.answer("❌ Питомец не найден.")
    
    food = await db_execute("SELECT happiness_boost, xp_boost, price FROM pet_items WHERE name = ?", (food_name,), fetchone=True)
    if not food:
        return await message.answer(f"❌ Еда <b>{food_name}</b> не найдена. Доступно: Обычный корм, Вкусняшка, Элитный корм")
    
    user_gold = await db_execute("SELECT gold FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if user_gold[0] < food[2]:
        return await message.answer(f"❌ Недостаточно золота. Нужно {food[2]}.")
    
    await db_execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (food[2], user_id))
    new_happiness = min(100, pet[1] + food[0])
    await db_execute("UPDATE player_pets SET happiness = ?, xp = xp + ? WHERE id = ?", (new_happiness, food[1], pet[0]))
    
    await message.answer(f"✅ {pet_name} покормлен! Счастье: {new_happiness}/100")

@admin_router.message(Command("pet_items"))
async def list_pet_items(message: types.Message):
    items = await db_execute("SELECT name, description, happiness_boost, xp_boost, price FROM pet_items", fetch=True)
    if not items:
        return await message.answer("🍖 Еды для питомцев нет.")
    
    text = "🍖 <b>ЕДА ДЛЯ ПИТОМЦЕВ:</b>\n\n"
    for row in items:
        name, desc, happ, xp, price = row
        text += f"🔹 <b>{name}</b> — {price} золота\n   {desc}\n   ❤️ +{happ} счастья | ✨ +{xp} XP\n\n"
    
    text += "<i>Использовать: /feed_pet [Питомец] [Еда]</i>"
    await message.answer(text)

# ============================================
# РЫНОК ИГРОКОВ (P2P)
# ============================================
@market_router.message(Command("player_market"))
async def player_market_view(message: types.Message):
    items = await db_execute(
        "SELECT pm.id, pm.item_name, pm.price, pm.quantity, pm.rarity, u.character_name "
        "FROM player_market pm JOIN users u ON pm.seller_id = u.user_id WHERE pm.is_sold = 0",
        fetch=True
    )
    if not items:
        return await message.answer("💱 Рынок игроков пуст.")
    
    text = "💱 <b>РЫНОК ИГРОКОВ:</b>\n\n"
    for row in items:
        item_id, name, price, qty, rarity, seller = row
        text += f" [ID: <b>{item_id}</b>] {RARITY_ICONS.get(rarity, '⚪')} <b>{name}</b>\n"
        text += f"   💰 {price} золота | x{qty}\n"
        text += f"   🏪 Продавец: {seller}\n\n"
    
    text += "<i>Купить: /buy_market [ID]\nПродать: /sell [Предмет] [Цена]</i>"
    await message.answer(text)

@market_router.message(Command("sell"))
async def player_sell_start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    char_name = await get_character(user_id)
    if not char_name:
        return await message.answer("Создай персонажа!")
    
    if not command.args:
        return await message.answer("Формат: /sell [Название предмета] [Цена]")
    
    args = command.args.rsplit(maxsplit=1)
    if len(args) < 2:
        return await message.answer("Формат: /sell [Предмет] [Цена]")
    
    item_name, price_str = args[0], args[1]
    try:
        price = int(price_str)
    except:
        return await message.answer(" Цена должна быть числом!")
    
    # Проверяем наличие
    item = await db_execute("SELECT quantity, rarity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name), fetchone=True)
    if not item or item[0] <= 0:
        return await message.answer(f"❌ У тебя нет предмета <b>{item_name}</b>.")
    
    quantity, rarity = item
    
    # Создаем лот
    await db_execute(
        "INSERT INTO player_market (seller_id, item_name, price, quantity, rarity) VALUES (?, ?, ?, ?, ?)",
        (user_id, item_name, price, quantity, rarity)
    )
    
    # Удаляем из инвентаря
    await db_execute("DELETE FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name))
    
    await message.answer(f"✅ <b>{item_name}</b> выставлен на продажу за {price} золота!")

@market_router.message(Command("buy_market"))
async def buy_from_player_market(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /buy_market [ID лота]")
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    room_id = await get_user_room(user_id)
    lot_id = int(command.args)
    
    lot = await db_execute(
        "SELECT seller_id, item_name, price, quantity, rarity FROM player_market WHERE id = ? AND is_sold = 0",
        (lot_id,), fetchone=True
    )
    if not lot:
        return await message.answer("❌ Лот не найден или уже продан.")
    
    seller_id, item_name, price, quantity, rarity = lot
    
    if seller_id == user_id:
        return await message.answer("❌ Нельзя купить у себя!")
    
    buyer_gold = await db_execute("SELECT gold FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if buyer_gold[0] < price:
        return await message.answer(f"❌ Недостаточно золота. Нужно {price}.")
    
    # Переводим золото
    await db_execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (price, user_id))
    await db_execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (price, seller_id))
    
    # Добавляем предмет покупателю
    existing = await db_execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name), fetchone=True)
    if existing:
        await db_execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_name = ?", (quantity, user_id, item_name))
    else:
        await db_execute("INSERT INTO inventory (user_id, item_name, quantity, rarity) VALUES (?, ?, ?, ?)", (user_id, item_name, quantity, rarity))
    
    # Помечаем как проданное
    await db_execute("UPDATE player_market SET is_sold = 1 WHERE id = ?", (lot_id,))
    
    seller_name = await get_character(seller_id) or "Неизвестный"
    buyer_name = await get_character(user_id) or "Неизвестный"
    
    msg = f" <b>{buyer_name}</b> покупает <b>{item_name}</b> x{quantity} у <b>{seller_name}</b> за {price} золота!"
    await broadcast_to_session(chat_id, msg, room_id)
    await log_message(chat_id, "СИСТЕМА", msg, room_id)

@market_router.message(Command("my_sales"))
async def my_sales(message: types.Message):
    user_id = message.from_user.id
    sales = await db_execute(
        "SELECT id, item_name, price, quantity, is_sold FROM player_market WHERE seller_id = ?",
        (user_id,), fetch=True
    )
    if not sales:
        return await message.answer(" У тебя нет лотов на рынке.")
    
    text = "🏪 <b>ТВОИ ЛОТЫ:</b>\n\n"
    for row in sales:
        lot_id, name, price, qty, sold = row
        status = "✅ Продано" if sold else "🟢 Активно"
        text += f"[ID: {lot_id}] <b>{name}</b> x{qty} — {price} золота — {status}\n"
    
    text += "\n<i>Снять: /cancel_sale [ID]</i>"
    await message.answer(text)

@market_router.message(Command("cancel_sale"))
async def cancel_sale(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /cancel_sale [ID лота]")
    
    user_id = message.from_user.id
    lot_id = int(command.args)
    
    lot = await db_execute("SELECT item_name, quantity, rarity FROM player_market WHERE id = ? AND seller_id = ? AND is_sold = 0", (lot_id, user_id), fetchone=True)
    if not lot:
        return await message.answer("❌ Лот не найден или уже продан.")
    
    item_name, quantity, rarity = lot
    
    # Возвращаем предмет
    existing = await db_execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name), fetchone=True)
    if existing:
        await db_execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_name = ?", (quantity, user_id, item_name))
    else:
        await db_execute("INSERT INTO inventory (user_id, item_name, quantity, rarity) VALUES (?, ?, ?, ?)", (user_id, item_name, quantity, rarity))
    
    # Удаляем лот
    await db_execute("DELETE FROM player_market WHERE id = ?", (lot_id,))
    
    await message.answer(f"✅ Лот <b>{item_name}</b> снят с продажи и возвращен в инвентарь.")

# ============================================
# ОСТАЛЬНЫЕ КОМАНДЫ (сокращенно - аналогично предыдущим версиям)
# ============================================
# ... (здесь должны быть все остальные команды: админки, бой, лор, локации, комнаты и т.д.)
# Для экономии места я их не дублирую, они такие же как в предыдущей версии

# ============================================
# ДОПОЛНЕННЫЕ КОМАНДЫ (ВОССТАНОВЛЕННЫЙ БЛОК)
# ============================================

# --- АДМИН И ПОЛЬЗОВАТЕЛИ ---
@admin_router.message(Command("add_admin"))
async def add_admin_cmd(message: types.Message, command: CommandObject):
    if message.from_user.id != SUPER_ADMIN_ID:
        return await message.answer("⛔ Только главный админ может назначать админов.")
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /add_admin [ID пользователя]")
    uid = int(command.args)
    if uid == SUPER_ADMIN_ID: return await message.answer("Это главный админ.")
    await db_execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (uid, SUPER_ADMIN_ID))
    invalidate_admin_cache(uid)
    await message.answer(f"✅ Пользователь ID {uid} назначен админом!")

@admin_router.message(Command("users"))
async def list_users(message: types.Message):
    if not await is_admin(message.from_user.id): return
    users = await db_execute("SELECT user_id, character_name, messages_count FROM users ORDER BY messages_count DESC LIMIT 20", fetch=True)
    text = "👥 <b>ТОП ПОЛЬЗОВАТЕЛЕЙ:</b>\n\n" + "\n".join([f"🔹 ID <code>{r[0]}</code> | {r[1] or 'Без имени'} | 💬 {r[2]}" for r in users])
    await message.answer(text)

@admin_router.message(Command("set_stats"))
async def set_player_stats(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    args = command.args.split() if command.args else []
    if len(args) != 4: return await message.answer("Формат: /set_stats [ID] [STR] [AGI] [INT]")
    try:
        await db_execute("UPDATE users SET strength=?, agility=?, intelligence=? WHERE user_id=?", (int(args[1]), int(args[2]), int(args[3]), int(args[0])))
        await message.answer(f"✅ Статы обновлены для ID {args[0]}.")
    except: await message.answer("Ошибка ввода.")

# --- ИГРОВЫЕ ДЕЙСТВИЯ ---
@admin_router.message(Command("roll"))
@player_router.message(Command("roll"))
async def roll_dice_cmd(message: types.Message, command: CommandObject):
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    char_name = await get_character(user_id) or "Неизвестный"
    bonus, stat_name, dice_str = 0, "", "1d20"
    
    if command.args:
        arg = command.args.lower().strip()
        if arg in ['str', 'сила', 'agi', 'ловкость', 'int', 'интеллект']:
            stats = await db_execute("SELECT strength, agility, intelligence FROM users WHERE user_id = ?", (user_id,), fetchone=True)
            if stats:
                if 'str' in arg or 'сила' in arg: bonus, stat_name = stats[0], "(Сила)"
                elif 'agi' in arg or 'ловк' in arg: bonus, stat_name = stats[1], "(Ловкость)"
                elif 'int' in arg or 'интел' in arg: bonus, stat_name = stats[2], "(Интеллект)"
        else: dice_str = arg
    
    rolls, mod, total = roll_dice(dice_str)
    final_total = total + bonus
    roll_text = f"<b>{rolls[0]}</b>" if len(rolls) == 1 else "[" + "+".join(str(r) for r in rolls) + "]"
    mod_text = f" {'+' if mod > 0 else ''}{mod}" if mod != 0 else ""
    bonus_text = f" + {bonus} {stat_name}" if bonus != 0 else ""
    
    await broadcast_to_session(chat_id, f"🎲 <b>{char_name}</b> бросает {dice_str}{mod_text}{bonus_text}:\n{roll_text} = <b>{final_total}</b>", room_id)

@admin_router.message(Command("use"))
@player_router.message(Command("use"))
async def use_item(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /use [Название]")
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    char_name = await get_character(user_id)
    if not char_name: return await message.answer("Создай персонажа!")
    
    item = await db_execute("SELECT id, quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, command.args.strip()), fetchone=True)
    if not item: return await message.answer("❌ У тебя нет такого предмета.")
    
    if item[1] > 1: await db_execute("UPDATE inventory SET quantity = quantity - 1 WHERE id = ?", (item[0],))
    else: await db_execute("DELETE FROM inventory WHERE id = ?", (item[0],))
    
    msg = f"🧪 <b>{char_name}</b> использует: <b>{command.args.strip()}</b>!"
    await broadcast_to_session(chat_id, msg, room_id)
    await log_message(chat_id, "СИСТЕМА", msg, room_id)

@admin_router.message(Command("equip"))
@player_router.message(Command("equip"))
async def equip_item(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /equip [Название]")
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    char_name = await get_character(user_id)
    if not char_name: return await message.answer("Создай персонажа!")
    
    item = await db_execute("SELECT id, is_equipped, item_name FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, command.args.strip()), fetchone=True)
    if not item: return await message.answer("❌ Такого предмета нет.")
    
    new_status = 0 if item[1] else 1
    await db_execute("UPDATE inventory SET is_equipped = ? WHERE id = ?", (new_status, item[0]))
    action = "снимает" if item[1] else "экипирует"
    msg = f"{'🎒' if item[1] else '⚔️'} <b>{char_name}</b> {action}: <b>{item[2]}</b>!"
    await broadcast_to_session(chat_id, msg, room_id)

@admin_router.message(Command("trade"))
@player_router.message(Command("trade"))
async def trade_item(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /trade [Имя] [Предмет]")
    args = command.args.split(maxsplit=1)
    if len(args) < 2: return await message.answer("Формат: /trade [Имя] [Предмет]")
    
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    target = await db_execute("SELECT user_id FROM users WHERE character_name = ?", (args[0],), fetchone=True)
    if not target or target[0] == user_id: return await message.answer("❌ Игрок не найден или это ты.")
    
    item = await db_execute("SELECT id, quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, args[1]), fetchone=True)
    if not item: return await message.answer(f"❌ У тебя нет <b>{args[1]}</b>.")
    
    if item[1] > 1: await db_execute("UPDATE inventory SET quantity = quantity - 1 WHERE id = ?", (item[0],))
    else: await db_execute("DELETE FROM inventory WHERE id = ?", (item[0],))
    
    inv = await db_execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (target[0], args[1]), fetchone=True)
    if inv: await db_execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_name = ?", (target[0], args[1]))
    else: await db_execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (target[0], args[1]))
    
    msg = f"🤝 <b>{await get_character(user_id)}</b> передаёт <b>{args[1]}</b> игроку <b>{args[0]}</b>!"
    await broadcast_to_session(chat_id, msg, room_id)

# --- БОЕВАЯ СИСТЕМА И ПАНЕЛЬ ---
@admin_router.message(Command("spawn"))
async def spawn_monster(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    args = command.args.split(maxsplit=1) if command.args else []
    if len(args) < 2 or not args[0].isdigit(): return await message.answer("Формат: /spawn [ХП] [Имя]")
    
    await db_execute("INSERT INTO session_monsters (chat_id, room_id, name, hp, max_hp) VALUES (?, ?, ?, ?, ?)", (chat_id, room_id, args[1], int(args[0]), int(args[0])))
    msg = f"🐉 <b>{args[1]}</b> (❤️ {args[0]}) появляется!"
    await broadcast_to_session(chat_id, msg, room_id)

@admin_router.message(Command("combat_start"))
async def combat_start(message: types.Message):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    
    players = await db_execute("SELECT u.user_id, u.character_name FROM users u JOIN session_players sp ON u.user_id = sp.user_id WHERE sp.status = 'player' AND sp.room_id = ? AND sp.chat_id = ?", (room_id, chat_id) if room_id > 0 else (0, chat_id), fetch=True)
    monsters = await db_execute("SELECT id, name FROM session_monsters WHERE room_id = ? AND chat_id = ?", (room_id, chat_id) if room_id > 0 else (0, chat_id), fetch=True)
    
    if not players and not monsters: return await message.answer("Нет участников.")
    s.combat_queue = [{'type': 'player', 'id': p[0], 'name': p[1]} for p in players] + [{'type': 'monster', 'id': m[0], 'name': m[1]} for m in monsters]
    random.shuffle(s.combat_queue)
    s.combat_active, s.current_turn_index = True, 0
    await broadcast_to_session(chat_id, "⚔️ <b>БОЙ НАЧАЛСЯ!</b>\n" + "\n".join([f"{i+1}. {e['name']}" for i, e in enumerate(s.combat_queue)]), room_id)
    await broadcast_to_session(chat_id, f"⏳ Ход: <u>{s.combat_queue[0]['name']}</u>", room_id)

@admin_router.message(Command("next_turn"))
async def next_turn(message: types.Message):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    if not s.combat_active or not s.combat_queue: return
    s.current_turn_index = (s.current_turn_index + 1) % len(s.combat_queue)
    await broadcast_to_session(chat_id, f"⏳ Ход: <u>{s.combat_queue[s.current_turn_index]['name']}</u>", room_id)

@admin_router.message(Command("panel"))
async def open_gm_panel(message: types.Message):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    
    players = await db_execute("SELECT u.user_id, u.character_name, u.hp, u.max_hp FROM users u JOIN session_players sp ON u.user_id = sp.user_id WHERE sp.status = 'player' AND sp.room_id = ? AND sp.chat_id = ?", (room_id, chat_id) if room_id > 0 else (0, chat_id), fetch=True)
    monsters = await db_execute("SELECT id, name, hp, max_hp FROM session_monsters WHERE room_id = ? AND chat_id = ?", (room_id, chat_id) if room_id > 0 else (0, chat_id), fetch=True)
    
    kb = [[InlineKeyboardButton(text=f"👤 {p[1]} ({p[2]}/{p[3]})", callback_data=f"gm_sel_player_{p[0]}")] for p in players]
    kb += [[InlineKeyboardButton(text=f"🐉 {m[1]} ({m[2]}/{m[3]})", callback_data=f"gm_sel_monster_{m[0]}")] for m in monsters]
    await message.answer("🛠 <b>Панель Мастера:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@admin_router.callback_query(F.data.startswith("gm_sel_"))
async def select_entity_action(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    await state.update_data(target_id=int(parts[3]), target_type=parts[2])
    kb = [[InlineKeyboardButton(text="⚔️ Урон", callback_data="gm_act_damage"), InlineKeyboardButton(text="💊 Хил", callback_data="gm_act_heal")]]
    if parts[2] == 'monster': kb.append([InlineKeyboardButton(text="💀 Убить", callback_data="gm_act_kill")])
    await callback.message.edit_text("Действие:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@admin_router.callback_query(F.data.startswith("gm_act_"))
async def gm_action_prompt(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    action = callback.data.split("_")[2]
    if action == "kill":
        data = await state.get_data()
        await db_execute("DELETE FROM session_monsters WHERE id = ?", (data['target_id'],))
        s = get_session(callback.message.chat.id, await get_user_room(callback.from_user.id))
        s.combat_queue = [q for q in s.combat_queue if not (q['type'] == 'monster' and q['id'] == data['target_id'])]
        await callback.message.edit_text("💀 Монстр уничтожен!")
        return
    await state.update_data(action_type=action)
    await state.set_state(GMAction.waiting_for_value)
    await callback.message.edit_text("Введи число (урон/хил):")

@admin_router.message(GMAction.waiting_for_value)
async def execute_gm_action(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    data = await state.get_data()
    if not message.text.isdigit(): return await message.answer("Нужно число!")
    amt = int(message.text)
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    
    if data['target_type'] == 'player':
        field = "hp" if data['action_type'] == "damage" else "hp" # Упрощено для примера
        # Для полноценного хила нужна отдельная логика, здесь базовый урон
        if data['action_type'] == "damage":
            await db_execute("UPDATE users SET hp = MAX(0, hp - ?) WHERE user_id = ?", (amt, data['target_id']))
            name = await get_character(data['target_id'])
            await broadcast_to_session(chat_id, f"💥 <b>{name}</b> получает {amt} урона!", room_id)
    await state.clear()
    await message.answer("✅ Выполнено.")

# --- ЛОР И ЛОКАЦИИ ---
@admin_router.message(Command("add_location"))
async def add_location(message: types.Message, command: CommandObject, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    if not command.args: return await message.answer("Формат: /add_location [Название] - [Описание]")
    name, desc = command.args.split("-", 1)
    await db_execute("INSERT OR REPLACE INTO locations (name, description) VALUES (?, ?)", (name.strip(), desc.strip()))
    await message.answer(f"✅ Локация <b>{name.strip()}</b> добавлена.")

@admin_router.message(Command("move"))
async def move_location(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /move [Название]")
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    loc = await db_execute("SELECT name, description FROM locations WHERE name = ?", (command.args.strip(),), fetchone=True)
    if not loc: return await message.answer("❌ Локация не найдена.")
    
    await db_execute("UPDATE users SET location = ? WHERE user_id = ?", (loc[0], user_id))
    s = get_session(chat_id, room_id)
    s.current_location = loc[0]
    await broadcast_to_session(chat_id, f"🚶 <b>{await get_character(user_id)}</b> перемещается в: <b>{loc[0]}</b>\n<i>{loc[1]}</i>", room_id)

@admin_router.message(Command("lore"))
async def read_lore(message: types.Message, command: CommandObject):
    if not command.args:
        topics = await db_execute("SELECT topic, category FROM lore", fetch=True)
        if not topics: return await message.answer("📚 Вики пуста.")
        return await message.answer("📚 <b>Статьи:</b>\n" + "\n".join([f"🔹 <code>{t[0]}</code> [{t[1]}]" for t in topics]) + "\n\n<i>Читай: /lore [название]</i>")
    
    res = await db_execute("SELECT description, category, views FROM lore WHERE topic = ?", (command.args.lower().strip(),), fetchone=True)
    if res:
        await db_execute("UPDATE lore SET views = views + 1 WHERE topic = ?", (command.args.lower().strip(),))
        await message.answer(f"📖 <b>{command.args}</b> [{res[1]}]\n👁 {res[2]+1}\n\n{res[0]}")
    else:
        await message.answer("❓ Статьи нет.")

# --- ПРОФИЛЬ/ПОИСК/ШЁПОТ ---
@admin_router.message(Command("location"))
@player_router.message(Command("location"))
async def show_location(message: types.Message):
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    loc = await db_execute("SELECT description, image_id FROM locations WHERE name = ?", (s.current_location,), fetchone=True)
    desc = loc[0] if loc and loc[0] else "Описание отсутствует."
    text = f"📍 <b>{s.current_location}</b>\n\n{desc}"
    if loc and loc[1]:
        await message.answer_photo(loc[1], caption=text)
    else:
        await message.answer(text)

@admin_router.message(Command("locations"))
async def list_locations(message: types.Message):
    if not await is_admin(message.from_user.id): return
    locs = await db_execute("SELECT name FROM locations", fetch=True)
    if not locs: return await message.answer("🗺 Локаций нет. Добавь через /add_location")
    await message.answer("🗺 <b>Локации:</b>\n" + "\n".join(f"🔹 {l[0]}" for l in locs))

@admin_router.message(Command("quest"))
@player_router.message(Command("quest"))
async def show_quest(message: types.Message):
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    key = f"quest_{get_session_key(chat_id, room_id)}"
    res = await db_execute("SELECT value FROM global_state WHERE key = ?", (key,), fetchone=True)
    text = res[0] if res else "Активных заданий нет."
    await message.answer(f"🎯 <b>ТЕКУЩЕЕ ЗАДАНИЕ:</b>\n\n{text}")

@admin_router.message(Command("set_quest"))
async def set_quest(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    if not command.args: return await message.answer("Формат: /set_quest [Описание задания]")
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    key = f"quest_{get_session_key(chat_id, room_id)}"
    await db_execute("INSERT OR REPLACE INTO global_state (key, value) VALUES (?, ?)", (key, command.args.strip()))
    await broadcast_to_session(chat_id, f"🎯 <b>Новое задание:</b>\n{command.args.strip()}", room_id)

@admin_router.message(Command("w"))
@player_router.message(Command("w"))
async def whisper_cmd(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /w [Имя] [Текст]")
    args = command.args.split(maxsplit=1)
    if len(args) < 2: return await message.answer("Формат: /w [Имя] [Текст]")
    target_name, text = args
    user_id = message.from_user.id
    sender_name = await get_character(user_id) or "Неизвестный"
    target = await db_execute("SELECT user_id FROM users WHERE character_name = ?", (target_name,), fetchone=True)
    if not target: return await message.answer("❌ Игрок не найден.")
    if target[0] == user_id: return await message.answer("❌ Нельзя шептать самому себе.")
    formatted = format_rp_text(text)
    try:
        await bot.send_message(target[0], f"🤫 <i>Шёпот от <b>{sender_name}</b>:</i>\n{formatted}")
    except Exception:
        return await message.answer("❌ Не удалось отправить (игрок не запускал бота).")
    await message.answer(f"🤫 Шёпот отправлен игроку <b>{target_name}</b>.")

@admin_router.message(Command("active"))
@player_router.message(Command("active"))
async def show_active(message: types.Message):
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    active_ids = await get_active_players(chat_id, room_id)
    if not active_ids: return await message.answer("В сессии никого нет.")
    names = [f"👤 {await get_character(uid) or 'Без имени'}" for uid in active_ids]
    await message.answer("👥 <b>В СЕССИИ:</b>\n" + "\n".join(names))

@admin_router.message(Command("find"))
@player_router.message(Command("find"))
async def find_player(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /find [Имя или ID]")
    query = command.args.strip()
    if query.isdigit():
        res = await db_execute("SELECT user_id, character_name, level, location FROM users WHERE user_id = ?", (int(query),), fetchone=True)
    else:
        res = await db_execute("SELECT user_id, character_name, level, location FROM users WHERE character_name = ?", (query,), fetchone=True)
    if not res: return await message.answer("❌ Не найден.")
    await message.answer(f"👤 <b>{res[1]}</b> (Ур. {res[2]})\n🆔 <code>{res[0]}</code>\n📍 {res[3]}")

# --- РЫНОК МАСТЕРА (GM SHOP) ---
@admin_router.message(Command("add_market"))
async def add_market_item(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    if not command.args or "-" not in command.args:
        return await message.answer("Формат: /add_market [Кол-во] [Цена] [Название] - [Описание] [Редкость]")
    head, rest = command.args.split("-", 1)
    head_parts = head.split(maxsplit=2)
    if len(head_parts) < 3 or not head_parts[0].isdigit() or not head_parts[1].isdigit():
        return await message.answer("Формат: /add_market [Кол-во] [Цена] [Название] - [Описание] [Редкость]")
    qty, price, name = int(head_parts[0]), int(head_parts[1]), head_parts[2].strip()
    rest_parts = rest.strip().rsplit(maxsplit=1)
    if len(rest_parts) == 2 and rest_parts[1].lower() in RARITY_NAMES:
        desc, rarity = rest_parts[0].strip(), rest_parts[1].lower()
    else:
        desc, rarity = rest.strip(), "common"
    await db_execute("INSERT INTO market (item_name, price, description, quantity, rarity) VALUES (?, ?, ?, ?, ?)", (name, price, desc, qty, rarity))
    await message.answer(f"✅ <b>{name}</b> добавлен на рынок ГМа: {price} золота x{qty}")

@market_router.message(Command("market"))
async def gm_market_view(message: types.Message):
    items = await db_execute("SELECT id, item_name, price, description, quantity, rarity FROM market WHERE quantity > 0", fetch=True)
    if not items: return await message.answer("🛒 Рынок ГМа пуст.")
    text = "🛒 <b>РЫНОК МАСТЕРА:</b>\n\n"
    for row in items:
        iid, name, price, desc, qty, rarity = row
        text += f"[ID: <b>{iid}</b>] {RARITY_ICONS.get(rarity, '⚪')} <b>{name}</b>\n   💰 {price} золота | В наличии: {qty}\n"
        if desc:
            text += f"   <i>{desc}</i>\n"
        text += "\n"
    text += "<i>Купить: /buy [ID]</i>"
    await message.answer(text)

@market_router.message(Command("buy"))
async def gm_market_buy(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /buy [ID]")
    user_id = message.from_user.id
    char_name = await get_character(user_id)
    if not char_name: return await message.answer("Создай персонажа!")
    item_id = int(command.args)
    item = await db_execute("SELECT item_name, price, quantity, rarity FROM market WHERE id = ?", (item_id,), fetchone=True)
    if not item or item[2] <= 0: return await message.answer("❌ Товар не найден или закончился.")
    name, price, qty, rarity = item
    gold = await db_execute("SELECT gold FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not gold or gold[0] < price: return await message.answer(f"❌ Недостаточно золота. Нужно {price}.")
    await db_execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (price, user_id))
    await db_execute("UPDATE market SET quantity = quantity - 1 WHERE id = ?", (item_id,))
    existing = await db_execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, name), fetchone=True)
    if existing:
        await db_execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_name = ?", (user_id, name))
    else:
        await db_execute("INSERT INTO inventory (user_id, item_name, quantity, rarity) VALUES (?, ?, 1, ?)", (user_id, name, rarity))
    await message.answer(f"✅ Куплено: <b>{name}</b> за {price} золота!")

# --- УПРАВЛЕНИЕ СЕССИЕЙ (ВРЕМЯ/ПОГОДА/СОБЫТИЯ/NPC) ---
@admin_router.message(Command("time"))
async def set_time(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    valid = ["утро", "день", "вечер", "ночь"]
    arg = command.args.lower().strip() if command.args else ""
    if arg not in valid:
        return await message.answer(f"Формат: /time [{'/'.join(valid)}]")
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    s.time_of_day = arg
    await broadcast_to_session(chat_id, f"🕐 Наступает <b>{s.time_of_day}</b>...", room_id)

@admin_router.message(Command("env"))
async def set_weather(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    valid = ["ясно", "дождь", "снег", "туман", "гроза"]
    arg = command.args.lower().strip() if command.args else ""
    if arg not in valid:
        return await message.answer(f"Формат: /env [{'/'.join(valid)}]")
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    s.weather = arg
    await broadcast_to_session(chat_id, f"🌤 Погода меняется: <b>{s.weather}</b>...", room_id)

@admin_router.message(Command("event"))
async def trigger_event(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    if not command.args: return await message.answer("Формат: /event [Текст события]")
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    s.ambient_text = command.args.strip()
    await broadcast_to_session(chat_id, f"⚡️ <b>СОБЫТИЕ:</b>\n<i>{s.ambient_text}</i>", room_id)

@admin_router.message(Command("npc"))
async def set_active_npc(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    if not command.args:
        s.active_npc = None
        return await message.answer("🎭 Режим NPC выключен.")
    s.active_npc = command.args.strip()
    await message.answer(f"🎭 Теперь ты говоришь как <b>{s.active_npc}</b> в сессии. Выключить: /npc")

@admin_router.message(Command("open_session"))
async def open_session(message: types.Message):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    s.combat_active = False
    s.combat_queue = []
    s.active_npc = None
    await broadcast_to_session(chat_id, "🎬 <b>Мастер открывает сессию!</b>\nПрисоединяйся: /join", room_id)

@admin_router.message(Command("archive"))
async def archive_session(message: types.Message):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    logs = await db_execute(
        "SELECT sender, message, timestamp FROM logs WHERE chat_id = ? AND room_id = ? ORDER BY id",
        (chat_id, room_id), fetch=True
    )
    if not logs:
        return await message.answer("📦 Лог сессии пуст, архивировать нечего.")
    content = "\n".join(f"[{row[2]}] {row[0]}: {row[1]}" for row in logs)
    file = BufferedInputFile(content.encode("utf-8"), filename=f"session_archive_{chat_id}_{room_id}.txt")
    await message.answer_document(file, caption="📦 Архив сессии.")
    await db_execute("DELETE FROM logs WHERE chat_id = ? AND room_id = ?", (chat_id, room_id))
    await broadcast_to_session(chat_id, "📦 <b>Сессия архивирована Мастером.</b>", room_id)

@admin_router.message(Command("broadcast"))
async def broadcast_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await state.set_state(GMBroadcast.waiting_message)
    await message.answer("📢 Введи текст рассылки для ВСЕХ пользователей (или /cancel):")

@admin_router.message(GMBroadcast.waiting_message, F.text)
async def broadcast_send(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    users = await db_execute("SELECT user_id FROM users", fetch=True)
    sent = 0
    for row in users:
        try:
            await bot.send_message(row[0], f"📢 <b>ОБЪЯВЛЕНИЕ МАСТЕРА:</b>\n\n{message.text}")
            sent += 1
            await asyncio.sleep(0.03)
        except Exception:
            pass
    await state.clear()
    await message.answer(f"✅ Рассылка отправлена: {sent}/{len(users)}")

# --- АДМИНЫ И СТАТИСТИКА ---
@admin_router.message(Command("remove_admin"))
async def remove_admin_cmd(message: types.Message, command: CommandObject):
    if message.from_user.id != SUPER_ADMIN_ID:
        return await message.answer("⛔ Только главный админ может снимать админов.")
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /remove_admin [ID пользователя]")
    uid = int(command.args)
    await db_execute("DELETE FROM admins WHERE user_id = ?", (uid,))
    invalidate_admin_cache(uid)
    await message.answer(f"✅ Пользователь ID {uid} больше не админ.")

@admin_router.message(Command("admins"))
async def list_admins(message: types.Message):
    if not await is_admin(message.from_user.id): return
    admins = await db_execute("SELECT user_id FROM admins", fetch=True)
    text = f"👑 Главный админ: <code>{SUPER_ADMIN_ID}</code>\n"
    text += "\n".join(f"🔸 <code>{a[0]}</code>" for a in admins) if admins else "Других админов нет."
    await message.answer(text)

@admin_router.message(Command("dashboard"))
async def dashboard(message: types.Message):
    if not await is_admin(message.from_user.id): return
    total_users = await db_execute("SELECT COUNT(*) FROM users", fetchone=True)
    total_players = await db_execute("SELECT COUNT(*) FROM session_players WHERE status='player'", fetchone=True)
    total_rooms = await db_execute("SELECT COUNT(*) FROM rooms WHERE is_active=1", fetchone=True)
    total_monsters = await db_execute("SELECT COUNT(*) FROM session_monsters", fetchone=True)
    text = (
        "📊 <b>ДАШБОРД</b>\n\n"
        f"👥 Персонажей: {total_users[0]}\n"
        f"⚔️ В сессиях: {total_players[0]}\n"
        f"🏠 Активных комнат: {total_rooms[0]}\n"
        f"🐉 Монстров в игре: {total_monsters[0]}\n"
        f"🎨 Pillow: {'✅' if PIL_AVAILABLE else '❌'}"
    )
    await message.answer(text)

@admin_router.message(Command("user_stats"))
async def user_stats(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /user_stats [ID]")
    uid = int(command.args)
    u = await db_execute(
        "SELECT character_name, hp, max_hp, xp, level, gold, strength, agility, intelligence, location, messages_count, created_at, last_active FROM users WHERE user_id = ?",
        (uid,), fetchone=True
    )
    if not u: return await message.answer("❌ Пользователь не найден.")
    name, hp, max_hp, xp, level, gold, s_, a_, i_, loc, msgs, created, active = u
    text = (
        f"📋 <b>{name}</b> (ID: <code>{uid}</code>)\n\n"
        f"❤️ HP: {hp}/{max_hp} | Ур. {level} | ✨ XP: {xp}\n"
        f"💪 {s_} 🏃 {a_} 🧠 {i_} | 🪙 {gold}\n"
        f"📍 {loc}\n"
        f"💬 Сообщений: {msgs}\n"
        f"📅 Создан: {created}\n"
        f"🕐 Активен: {active}\n"
        f"🛠 Админ: {'Да' if await is_admin(uid) else 'Нет'}"
    )
    await message.answer(text)

# --- КОМНАТЫ ---
@room_router.message(Command("room_create"))
async def room_create_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await get_user_room(user_id):
        return await message.answer("⚠️ Ты уже в комнате. Сначала /room_leave")
    await state.set_state(RoomCreate.waiting_name)
    await message.answer("🏠 Введи название новой комнаты (или /cancel):")

@room_router.message(RoomCreate.waiting_name, F.text)
async def room_create_finish(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    user_id, chat_id = message.from_user.id, message.chat.id
    name = message.text.strip()
    await db_execute("INSERT INTO rooms (name, owner_id) VALUES (?, ?)", (name, user_id))
    room = await db_execute("SELECT id FROM rooms WHERE name = ? ORDER BY id DESC LIMIT 1", (name,), fetchone=True)
    room_id = room[0]
    await db_execute("INSERT OR IGNORE INTO room_members (room_id, user_id, role) VALUES (?, ?, 'owner')", (room_id, user_id))
    await db_execute("INSERT OR REPLACE INTO session_players (user_id, status, chat_id, room_id) VALUES (?, 'player', ?, ?)", (user_id, chat_id, room_id))
    await state.clear()
    await message.answer(f"✅ Комната <b>{name}</b> создана (ID {room_id})! Ты автоматически вошёл в неё.")

@room_router.message(Command("room_list"))
async def room_list(message: types.Message):
    rooms = await db_execute("SELECT id, name FROM rooms WHERE is_active = 1", fetch=True)
    if not rooms: return await message.answer("🏠 Комнат нет.")
    await message.answer("🏠 <b>Комнаты:</b>\n" + "\n".join([f"🔹 ID <code>{r[0]}</code> — <b>{r[1]}</b>" for r in rooms]) + "\n\n<i>Войти: /room_join [ID]</i>")

@room_router.message(Command("room_join"))
async def room_join(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit(): return await message.answer("Формат: /room_join [ID]")
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = int(command.args)
    if await get_user_room(user_id): return await message.answer("⚠️ Сначала /room_leave")
    
    room = await db_execute("SELECT name FROM rooms WHERE id = ? AND is_active = 1", (room_id,), fetchone=True)
    if not room: return await message.answer("❌ Комната не найдена.")
    
    await db_execute("INSERT OR IGNORE INTO room_members (room_id, user_id, role) VALUES (?, ?, 'member')", (room_id, user_id))
    await db_execute("UPDATE session_players SET room_id = ? WHERE user_id = ?", (room_id, user_id))
    await message.answer(f"✅ Ты в комнате <b>{room[0]}</b>!")

@room_router.message(Command("room_leave"))
async def room_leave(message: types.Message):
    user_id = message.from_user.id
    room_id = await get_user_room(user_id)
    if not room_id: return await message.answer("⚠️ Ты не в комнате.")
    
    await db_execute("UPDATE session_players SET room_id = 0 WHERE user_id = ?", (user_id,))
    await message.answer("✅ Ты вышел из комнаты.")

# ============================================
# РП ЧАТ
# ============================================
@rp_router.message(RPState.in_session)
async def rp_chat_router(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith('/'):
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    room_id = await get_user_room(user_id)
    active_players = await get_active_players(chat_id, room_id)
    all_users = await get_all_session_users(chat_id, room_id)
    
    if user_id not in active_players:
        if user_id in all_users:
            return
        await state.clear()
        return await message.answer("🛑 Сессия закрыта.")
    
    await update_user_activity(user_id)
    s = get_session(chat_id, room_id)
    
    if await is_admin(user_id) and s.active_npc:
        char_name = s.active_npc
        icon = "🎭"
    else:
        char_name = await get_character(user_id) or "Неизвестный"
        icon = "👤"
    
    header = await get_session_header(chat_id, room_id)
    formatted_text = format_rp_text(message.text) if message.text else ""
    final_msg = f"{header}\n{icon} <b>[{char_name}]:</b> {formatted_text}" if formatted_text else None
    
    if formatted_text:
        await log_message(chat_id, char_name, formatted_text, room_id)
    
    for pid in all_users:
        if pid != user_id:
            try:
                if message.photo:
                    await bot.send_photo(pid, message.photo[-1].file_id, caption=f"{header}\n{icon} <b>[{char_name}]:</b> {message.caption or ''}")
                elif message.text:
                    await bot.send_message(pid, final_msg)
                else:
                    await message.copy_to(pid)
                await asyncio.sleep(0.03)
            except:
                pass

# ============================================
# ERROR HANDLER
# ============================================
@dp.error()
async def on_error(update: types.Update, exception: Exception):
    print(f"❌ Ошибка: {exception}")
    try:
        if update.message:
            await update.message.answer("⚠️ Техническая ошибка.")
    except:
        pass
    return True

# ============================================
# MAIN
# ============================================
async def main():
    init_db()
    await set_bot_commands(bot)
    print("🚀 Бот запущен!")
    print(f"👑 Админ: {SUPER_ADMIN_ID}")
    print(f"🎨 Pillow: {'✅' if PIL_AVAILABLE else '❌'}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())