from shared import *

@admin_router.message(Command("users"))
async def list_users(message: types.Message):
    if not await is_admin(message.from_user.id): return
    users = await db_execute("SELECT user_id, character_name, messages_count FROM users ORDER BY messages_count DESC LIMIT 20", fetch=True)
    text = "👥 <b>ТОП ПОЛЬЗОВАТЕЛЕЙ:</b>\n\n" + "\n".join([f"🔹 ID <code>{r[0]}</code> | {r[1] or 'Без имени'} | 💬 {r[2]}" for r in users])
    await message.answer(text)

