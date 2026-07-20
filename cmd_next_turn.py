from shared import *

@admin_router.message(Command("next_turn"))
async def next_turn(message: types.Message):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    if not s.combat_active or not s.combat_queue: return
    s.current_turn_index = (s.current_turn_index + 1) % len(s.combat_queue)
    await broadcast_to_session(chat_id, f"⏳ Ход: <u>{s.combat_queue[s.current_turn_index]['name']}</u>", room_id)

