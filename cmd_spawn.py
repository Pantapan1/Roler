from shared import *

@admin_router.message(Command("spawn"))
async def spawn_monster(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    args = command.args.split(maxsplit=1) if command.args else []
    if len(args) < 2 or not args[0].isdigit(): return await message.answer("Формат: /spawn [ХП] [Имя]")
    
    await db_execute("INSERT INTO session_monsters (chat_id, room_id, name, hp, max_hp) VALUES (?, ?, ?, ?, ?)", (chat_id, room_id, args[1], int(args[0]), int(args[0])))
    msg = f"🐉 <b>{args[1]}</b> (❤️ {args[0]}) появляется!"
    await broadcast_to_session(chat_id, msg, room_id)

