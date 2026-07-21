from shared import *

@admin_router.message(Command("panel"))
async def open_gm_panel(message: types.Message):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    
    players = await db_execute("SELECT u.user_id, u.character_name, u.hp, u.max_hp FROM users u JOIN session_players sp ON u.user_id = sp.user_id WHERE sp.status = 'player' AND sp.room_id = ?", (room_id,), fetch=True)
    monsters = await db_execute("SELECT id, name, hp, max_hp FROM session_monsters WHERE room_id = ?", (room_id,), fetch=True)
    
    kb = [[InlineKeyboardButton(text=f"👤 {p[1]} ({p[2]}/{p[3]})", callback_data=f"gm_sel_player_{p[0]}")] for p in players]
    kb += [[InlineKeyboardButton(text=f"🐉 {m[1]} ({m[2]}/{m[3]})", callback_data=f"gm_sel_monster_{m[0]}")] for m in monsters]
    await message.answer("🛠 <b>Панель Мастера:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

