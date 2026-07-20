from shared import *

@rp_router.message(RPState.in_session)
async def rp_chat_router(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith('/'):
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    room_id = await get_user_room(user_id)
    active_players = await get_active_players(chat_id, room_id)
    all_users = await get_all_session_users(chat_id, room_id)
    
    if user_id not in active_players:
        if user_id in all_users:
            return
        await state.clear()
        return await message.answer("🛑 Сессия закрыта.")
    
    await update_user_activity(user_id)
    s = get_session(chat_id, room_id)
    
    if await is_admin(user_id) and s.active_npc:
        char_name = s.active_npc
        icon = "🎭"
    else:
        char_name = await get_character(user_id) or "Неизвестный"
        icon = "👤"
    
    header = await get_session_header(chat_id, room_id)
    formatted_text = format_rp_text(message.text) if message.text else ""
    final_msg = f"{header}\n{icon} <b>[{char_name}]:</b> {formatted_text}" if formatted_text else None
    
    if formatted_text:
        await log_message(chat_id, char_name, formatted_text, room_id)
    
    for pid in all_users:
        if pid != user_id:
            try:
                if message.photo:
                    await bot.send_photo(pid, message.photo[-1].file_id, caption=f"{header}\n{icon} <b>[{char_name}]:</b> {message.caption or ''}")
                elif message.text:
                    await bot.send_message(pid, final_msg)
                else:
                    await message.copy_to(pid)
                await asyncio.sleep(0.03)
            except:
                pass

