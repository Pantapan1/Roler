from shared import *

@admin_router.message(Command("set_quest"))
async def set_quest(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    if not command.args: return await message.answer("Формат: /set_quest [Описание задания]")
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    key = f"quest_{get_session_key(chat_id, room_id)}"
    await db_execute("INSERT OR REPLACE INTO global_state (key, value) VALUES (?, ?)", (key, command.args.strip()))
    await broadcast_to_session(chat_id, f"🎯 <b>Новое задание:</b>\n{command.args.strip()}", room_id)

