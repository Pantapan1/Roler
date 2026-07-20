from shared import *

@admin_router.message(Command("location"))
@player_router.message(Command("location"))
async def show_location(message: types.Message):
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    loc = await db_execute("SELECT description, image_id FROM locations WHERE name = ?", (s.current_location,), fetchone=True)
    desc = loc[0] if loc and loc[0] else "Описание отсутствует."
    text = f"📍 <b>{s.current_location}</b>\n\n{desc}"
    if loc and loc[1]:
        await message.answer_photo(loc[1], caption=text)
    else:
        await message.answer(text)

