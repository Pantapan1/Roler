from shared import *

@admin_router.message(Command("time"))
async def set_time(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    valid = ["утро", "день", "вечер", "ночь"]
    arg = command.args.lower().strip() if command.args else ""
    if arg not in valid:
        return await message.answer(f"Формат: /time [{'/'.join(valid)}]")
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    s.time_of_day = arg
    await broadcast_to_session(chat_id, f"🕐 Наступает <b>{s.time_of_day}</b>...", room_id)

