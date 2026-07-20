from shared import *

@admin_router.message(Command("trade"))
@player_router.message(Command("trade"))
async def trade_item(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /trade [Имя] [Предмет]")
    args = command.args.split(maxsplit=1)
    if len(args) < 2: return await message.answer("Формат: /trade [Имя] [Предмет]")
    
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    target = await db_execute("SELECT user_id FROM users WHERE character_name = ?", (args[0],), fetchone=True)
    if not target or target[0] == user_id: return await message.answer("❌ Игрок не найден или это ты.")
    
    item = await db_execute("SELECT id, quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, args[1]), fetchone=True)
    if not item: return await message.answer(f"❌ У тебя нет <b>{args[1]}</b>.")
    
    if item[1] > 1: await db_execute("UPDATE inventory SET quantity = quantity - 1 WHERE id = ?", (item[0],))
    else: await db_execute("DELETE FROM inventory WHERE id = ?", (item[0],))
    
    inv = await db_execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (target[0], args[1]), fetchone=True)
    if inv: await db_execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_name = ?", (target[0], args[1]))
    else: await db_execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (target[0], args[1]))
    
    msg = f"🤝 <b>{await get_character(user_id)}</b> передаёт <b>{args[1]}</b> игроку <b>{args[0]}</b>!"
    await broadcast_to_session(chat_id, msg, room_id)

