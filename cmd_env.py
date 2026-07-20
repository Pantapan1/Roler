from shared import *

@admin_router.message(Command("env"))
async def set_weather(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    valid = ["ясно", "дождь", "снег", "туман", "гроза"]
    arg = command.args.lower().strip() if command.args else ""
    if arg not in valid:
        return await message.answer(f"Формат: /env [{'/'.join(valid)}]")
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    s.weather = arg
    await broadcast_to_session(chat_id, f"🌤 Погода меняется: <b>{s.weather}</b>...", room_id)

