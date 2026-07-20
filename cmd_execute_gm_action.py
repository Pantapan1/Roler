from shared import *

@admin_router.message(GMAction.waiting_for_value)
async def execute_gm_action(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    data = await state.get_data()
    if not message.text.isdigit(): return await message.answer("Нужно число!")
    amt = int(message.text)
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    
    if data['target_type'] == 'player':
        field = "hp" if data['action_type'] == "damage" else "hp" # Упрощено для примера
        # Для полноценного хила нужна отдельная логика, здесь базовый урон
        if data['action_type'] == "damage":
            await db_execute("UPDATE users SET hp = MAX(0, hp - ?) WHERE user_id = ?", (amt, data['target_id']))
            name = await get_character(data['target_id'])
            await broadcast_to_session(chat_id, f"💥 <b>{name}</b> получает {amt} урона!", room_id)
    await state.clear()
    await message.answer("✅ Выполнено.")

