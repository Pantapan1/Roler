from shared import *

@room_router.message(RoomCreate.waiting_name, F.text)
async def room_create_finish(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    user_id, chat_id = message.from_user.id, message.chat.id
    name = message.text.strip()
    await db_execute("INSERT INTO rooms (name, owner_id) VALUES (?, ?)", (name, user_id))
    room = await db_execute("SELECT id FROM rooms WHERE name = ? ORDER BY id DESC LIMIT 1", (name,), fetchone=True)
    room_id = room[0]
    await db_execute("INSERT OR IGNORE INTO room_members (room_id, user_id, role) VALUES (?, ?, 'owner')", (room_id, user_id))
    await db_execute("INSERT OR REPLACE INTO session_players (user_id, status, chat_id, room_id) VALUES (?, 'player', ?, ?)", (user_id, chat_id, room_id))
    await state.clear()
    await message.answer(f"✅ Комната <b>{name}</b> создана (ID {room_id})! Ты автоматически вошёл в неё.")

