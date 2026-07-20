from shared import *

@room_router.message(Command("room_leave"))
async def room_leave(message: types.Message):
    user_id = message.from_user.id
    room_id = await get_user_room(user_id)
    if not room_id: return await message.answer("⚠️ Ты не в комнате.")
    
    await db_execute("UPDATE session_players SET room_id = 0 WHERE user_id = ?", (user_id,))
    await message.answer("✅ Ты вышел из комнаты.")

