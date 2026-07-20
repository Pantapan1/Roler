from shared import *

@admin_router.message(Command("move"))
async def move_location(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /move [Название]")
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    loc = await db_execute("SELECT name, description FROM locations WHERE name = ?", (command.args.strip(),), fetchone=True)
    if not loc: return await message.answer("❌ Локация не найдена.")
    
    await db_execute("UPDATE users SET location = ? WHERE user_id = ?", (loc[0], user_id))
    s = get_session(chat_id, room_id)
    s.current_location = loc[0]
    await broadcast_to_session(chat_id, f"🚶 <b>{await get_character(user_id)}</b> перемещается в: <b>{loc[0]}</b>\n<i>{loc[1]}</i>", room_id)

