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
class LootBoxCreate(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_items = State()
class CardPackCreate(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_cards = State()
class MarketSell(StatesGroup):
    waiting_item = State()
    waiting_price = State()
class PetFeed(StatesGroup):
    waiting_food = State()
class PetCreate(StatesGroup):
    waiting_name = State()
    waiting_desc = State()
    waiting_rarity = State()
    waiting_stats = State()
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
async def get_user_room(user_id: int) -> int:
    res = await db_execute("SELECT room_id FROM session_players WHERE user_id = ? AND room_id > 0", (user_id,), fetchone=True)
    return res[0] if res else 0
async def log_message(chat_id: int, sender: str, text: str, room_id: int = 0):
    await db_execute("INSERT INTO logs (chat_id, room_id, sender, message) VALUES (?, ?, ?, ?)", (chat_id, room_id, sender, text))
async def update_user_activity(user_id: int):
    await db_execute("UPDATE users SET last_active = CURRENT_TIMESTAMP, messages_count = messages_count + 1 WHERE user_id = ?", (user_id,))
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
