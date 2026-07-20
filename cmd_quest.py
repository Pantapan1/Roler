from shared import *

@admin_router.message(Command("quest"))
@player_router.message(Command("quest"))
async def show_quest(message: types.Message):
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    key = f"quest_{get_session_key(chat_id, room_id)}"
    res = await db_execute("SELECT value FROM global_state WHERE key = ?", (key,), fetchone=True)
    text = res[0] if res else "Активных заданий нет."
    await message.answer(f"🎯 <b>ТЕКУЩЕЕ ЗАДАНИЕ:</b>\n\n{text}")

