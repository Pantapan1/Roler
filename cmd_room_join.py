from shared import *

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

