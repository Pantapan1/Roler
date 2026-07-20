from shared import *

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

