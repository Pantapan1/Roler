from shared import *

@admin_router.message(Command("archive"))
async def archive_session(message: types.Message):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    logs = await db_execute(
        "SELECT sender, message, timestamp FROM logs WHERE chat_id = ? AND room_id = ? ORDER BY id",
        (chat_id, room_id), fetch=True
    )
    if not logs:
        return await message.answer("📦 Лог сессии пуст, архивировать нечего.")
    content = "\n".join(f"[{row[2]}] {row[0]}: {row[1]}" for row in logs)
    file = BufferedInputFile(content.encode("utf-8"), filename=f"session_archive_{chat_id}_{room_id}.txt")
    await message.answer_document(file, caption="📦 Архив сессии.")
    await db_execute("DELETE FROM logs WHERE chat_id = ? AND room_id = ?", (chat_id, room_id))
    await broadcast_to_session(chat_id, "📦 <b>Сессия архивирована Мастером.</b>", room_id)

