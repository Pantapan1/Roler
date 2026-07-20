from shared import *

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

