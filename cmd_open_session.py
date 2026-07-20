from shared import *

@admin_router.message(Command("open_session"))
async def open_session(message: types.Message):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    s.combat_active = False
    s.combat_queue = []
    s.active_npc = None
    await broadcast_to_session(chat_id, "🎬 <b>Мастер открывает сессию!</b>\nПрисоединяйся: /join", room_id)

