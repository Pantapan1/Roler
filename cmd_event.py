from shared import *

@admin_router.message(Command("event"))
async def trigger_event(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    if not command.args: return await message.answer("Формат: /event [Текст события]")
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    s.ambient_text = command.args.strip()
    await broadcast_to_session(chat_id, f"⚡️ <b>СОБЫТИЕ:</b>\n<i>{s.ambient_text}</i>", room_id)

