from shared import *

@admin_router.message(Command("active"))
@player_router.message(Command("active"))
async def show_active(message: types.Message):
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    active_ids = await get_active_players(chat_id, room_id)
    if not active_ids: return await message.answer("В сессии никого нет.")
    names = [f"👤 {await get_character(uid) or 'Без имени'}" for uid in active_ids]
    await message.answer("👥 <b>В СЕССИИ:</b>\n" + "\n".join(names))

