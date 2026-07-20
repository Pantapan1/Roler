from shared import *

@admin_router.message(Command("equip"))
@player_router.message(Command("equip"))
async def equip_item(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /equip [Название]")
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    char_name = await get_character(user_id)
    if not char_name: return await message.answer("Создай персонажа!")
    
    item = await db_execute("SELECT id, is_equipped, item_name FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, command.args.strip()), fetchone=True)
    if not item: return await message.answer("❌ Такого предмета нет.")
    
    new_status = 0 if item[1] else 1
    await db_execute("UPDATE inventory SET is_equipped = ? WHERE id = ?", (new_status, item[0]))
    action = "снимает" if item[1] else "экипирует"
    msg = f"{'🎒' if item[1] else '⚔️'} <b>{char_name}</b> {action}: <b>{item[2]}</b>!"
    await broadcast_to_session(chat_id, msg, room_id)

