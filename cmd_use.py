from shared import *

@admin_router.message(Command("use"))
@player_router.message(Command("use"))
async def use_item(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /use [Название]")
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    char_name = await get_character(user_id)
    if not char_name: return await message.answer("Создай персонажа!")
    
    item = await db_execute("SELECT id, quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, command.args.strip()), fetchone=True)
    if not item: return await message.answer("❌ У тебя нет такого предмета.")
    
    if item[1] > 1: await db_execute("UPDATE inventory SET quantity = quantity - 1 WHERE id = ?", (item[0],))
    else: await db_execute("DELETE FROM inventory WHERE id = ?", (item[0],))
    
    msg = f"🧪 <b>{char_name}</b> использует: <b>{command.args.strip()}</b>!"
    await broadcast_to_session(chat_id, msg, room_id)
    await log_message(chat_id, "СИСТЕМА", msg, room_id)

