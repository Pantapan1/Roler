from shared import *

@room_router.message(Command("room_list"))
async def room_list(message: types.Message):
    rooms = await db_execute("SELECT id, name FROM rooms WHERE is_active = 1", fetch=True)
    if not rooms: return await message.answer("🏠 Комнат нет.")
    await message.answer("🏠 <b>Комнаты:</b>\n" + "\n".join([f"🔹 ID <code>{r[0]}</code> — <b>{r[1]}</b>" for r in rooms]) + "\n\n<i>Войти: /room_join [ID]</i>")

