from shared import *

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

