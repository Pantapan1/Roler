from shared import *

@admin_router.message(Command("join"))
@player_router.message(Command("join"))
async def join_session(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    user_id = message.from_user.id
    char_name = await get_character(user_id)
    if not char_name:
        return await message.answer("Сначала создай персонажа через /create")
    
    current_room = await get_user_room(user_id)
    if current_room:
        return await message.answer(f"⚠️ Ты в комнате ID {current_room}. Сначала /room_leave")
    
    await db_execute(
        "INSERT OR REPLACE INTO session_players (user_id, status, chat_id, room_id) VALUES (?, ?, ?, 0)",
        (user_id, 'player', chat_id)
    )
    await state.set_state(RPState.in_session)
    
    all_users = await get_all_session_users(chat_id)
    for pid in all_users:
        if pid != user_id:
            try:
                await bot.send_message(pid, f"<i> {char_name} присоединяется.</i>")
            except:
                pass
    await message.answer(f"✅ Ты вошел как <b>{char_name}</b>.")

